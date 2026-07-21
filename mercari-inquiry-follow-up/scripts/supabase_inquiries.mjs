#!/usr/bin/env node
/** Read and update canonical inquiry records through Supabase PostgREST. */

import fs from "node:fs";
import path from "node:path";

const PAGE_SIZE = 200;
const TABLE = "inquiries";
const DB_WRITES_SWITCH = "INQUIRY_FOLLOWUP_DB_WRITES_ENABLED";
const EXTERNAL_SEND_SWITCH = "INQUIRY_EXTERNAL_SEND_ENABLED";
const OPERATIONAL_SELECT = [
  "id",
  "inquiry_date",
  "status",
  "automation_status",
  "follow_up_status",
  "shop_key",
  "customer_nickname",
  "inquiry_type",
  "url",
  "product_name_snapshot",
  "units",
  "last_custom_message",
  "message_log_raw",
  "inquiry_body",
  "reply_strategy",
  "draft_reply",
  "inquiry_skill_reply",
  "follow_up_sent_at",
  "order_id",
  "mercari_product_id",
  "mercari_variant_name",
  "notes",
  "extra",
  "inquiry_product_links(item_code_snapshot,product_name_snapshot,is_primary,product_variant_id)",
].join(",");

function parseArgs(argv) {
  const command = argv[0];
  const options = {};
  for (let index = 1; index < argv.length; index += 1) {
    const argument = argv[index];
    if (!argument.startsWith("--")) throw new Error(`Unexpected argument: ${argument}`);
    const key = argument.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) options[key] = true;
    else {
      options[key] = next;
      index += 1;
    }
  }
  return { command, options };
}

function loadEnvFile(filePath) {
  if (!filePath) return {};
  if (!fs.existsSync(filePath)) throw new Error(`Environment file does not exist: ${filePath}`);
  const values = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    let value = match[2].trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    values[match[1]] = value;
  }
  return values;
}

function explicitlyEnabled(environment, key) {
  return String(environment[key] ?? "").trim().toLowerCase() === "true";
}

function requirePositiveInteger(value, label = "id") {
  const normalized = String(value ?? "").trim();
  if (!/^[1-9][0-9]*$/.test(normalized)) throw new Error(`Invalid ${label}: ${value}`);
  return normalized;
}

function requireDate(value, label) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value))) throw new Error(`Invalid ${label}: ${value}`);
  const [year, month, day] = String(value).split("-").map(Number);
  const checked = new Date(Date.UTC(year, month - 1, day));
  if (
    checked.getUTCFullYear() !== year
    || checked.getUTCMonth() !== month - 1
    || checked.getUTCDate() !== day
  ) throw new Error(`Invalid ${label}: ${value}`);
  return String(value);
}

function addUtcDays(date, days) {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

function todayInJst(offsetDays = 0) {
  const now = new Date();
  const jstCalendar = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  return addUtcDays(jstCalendar.toISOString().slice(0, 10), offsetDays);
}

function jstMidnightUtc(date) {
  return new Date(`${requireDate(date, "date")}T00:00:00+09:00`).toISOString();
}

function dateInJst(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function writePrivateJson(filePath, value) {
  const resolved = path.resolve(filePath);
  fs.mkdirSync(path.dirname(resolved), { recursive: true, mode: 0o700 });
  fs.writeFileSync(resolved, `${JSON.stringify(value, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  fs.chmodSync(resolved, 0o600);
}

function operationalRow(row) {
  const links = Array.isArray(row.inquiry_product_links) ? row.inquiry_product_links : [];
  const primaryLink = links.find((link) => link.is_primary) ?? links[0] ?? null;
  return {
    id: row.id,
    inquiryDate: dateInJst(row.inquiry_date),
    status: row.status,
    automationStatus: row.automation_status,
    followUpStatus: row.follow_up_status,
    shop: row.shop_key,
    customerName: row.customer_nickname,
    inquiryType: row.inquiry_type,
    url: row.url,
    productName: primaryLink?.product_name_snapshot ?? row.product_name_snapshot,
    itemCode: primaryLink?.item_code_snapshot ?? null,
    productVariantId: primaryLink?.product_variant_id ?? null,
    units: row.units,
    lastCustomerMessage: row.last_custom_message,
    messageLog: row.message_log_raw,
    inquiryBody: row.inquiry_body,
    replyStrategy: row.reply_strategy,
    draftReply: row.draft_reply,
    inquirySkillReply: row.inquiry_skill_reply,
    followUpDate: row.follow_up_sent_at,
    orderId: row.order_id,
    mercariProductId: row.mercari_product_id,
    mercariVariantName: row.mercari_variant_name,
    notes: row.notes,
    extra: row.extra ?? {},
  };
}

function validateAction(action, dryRun) {
  if (!action || typeof action !== "object" || Array.isArray(action)) throw new Error("Each status action must be an object");
  const id = requirePositiveInteger(action.id, "row id");
  const status = String(action.status ?? "");
  const allowed = new Set(["followed_up", "do_not_follow_up", "open", "closed_won", "closed_lose"]);
  if (!allowed.has(status)) throw new Error(`Invalid status for inquiry ${id}: ${status}`);
  if (status === "followed_up" && !dryRun && action.sendConfirmed !== true) {
    throw new Error(`Inquiry ${id} cannot be marked followed_up without sendConfirmed=true after visible confirmation`);
  }
  let followUpDate = null;
  if (action.followUpDate !== undefined) {
    const parsed = new Date(action.followUpDate);
    if (Number.isNaN(parsed.getTime())) throw new Error(`Invalid followUpDate for inquiry ${id}`);
    followUpDate = parsed.toISOString();
  }
  return { id, status, sendConfirmed: action.sendConfirmed === true, followUpDate };
}

function patchContract(action, now) {
  const filters = {
    id: `eq.${action.id}`,
    deleted_at: "is.null",
  };
  let payload;
  if (action.status === "followed_up") {
    filters.status = "eq.answered";
    filters.follow_up_status = "eq.open";
    payload = {
      status: "followed_up",
      follow_up_status: "followed_up",
      follow_up_sent_at: action.followUpDate ?? now,
    };
  } else if (action.status === "open") {
    filters.follow_up_status = "neq.open";
    payload = { follow_up_status: "open" };
  } else if (action.status === "do_not_follow_up") {
    filters.follow_up_status = "eq.open";
    payload = { follow_up_status: "do_not_follow_up" };
  } else {
    filters.status = "not.in.(closed_won,closed_lose)";
    payload = { status: action.status };
  }
  return { filters, payload };
}

const { command, options } = parseArgs(process.argv.slice(2));
if (!command || options.help) {
  console.log(`Usage:
  node supabase_inquiries.mjs query [--start YYYY-MM-DD] [--end YYYY-MM-DD] --output FILE
  node supabase_inquiries.mjs get --id ROW_ID --output FILE
  node supabase_inquiries.mjs preflight-send
  node supabase_inquiries.mjs batch-status --input FILE [--dry-run]
  node supabase_inquiries.mjs verify-status --input FILE [--output FILE]

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  SUPABASE_REST_URL  (optional explicit PostgREST root for local validation)
  INQUIRY_FOLLOWUP_DB_WRITES_ENABLED=true  (required for actual writes)
  INQUIRY_EXTERNAL_SEND_ENABLED=true       (also required for followed_up writes)

An environment file is read only when --env-file FILE is supplied.
The default candidate gate is status=answered, follow_up_status=open, deleted_at IS NULL.
The default query window is N-5 through N-2 inclusive in Asia/Tokyo.`);
  process.exit(command ? 0 : 2);
}

const fileEnv = options["env-file"] ? loadEnvFile(options["env-file"]) : {};
const environment = { ...fileEnv, ...process.env };
const supabaseUrl = String(environment.SUPABASE_URL ?? "").replace(/\/$/, "");
const supabaseKey = String(environment.SUPABASE_SERVICE_ROLE_KEY ?? "");
if (!supabaseUrl || !supabaseKey) throw new Error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
const baseUrl = String(environment.SUPABASE_REST_URL ?? `${supabaseUrl}/rest/v1`).replace(/\/$/, "");

async function api(relativePath, init = {}) {
  const response = await fetch(`${baseUrl}${relativePath}`, {
    ...init,
    headers: {
      apikey: supabaseKey,
      Authorization: `Bearer ${supabaseKey}`,
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = (await response.text()).slice(0, 800);
    throw new Error(`Supabase ${response.status} ${response.statusText}: ${body}`);
  }
  if (response.status === 204) return null;
  const body = await response.text();
  return body ? JSON.parse(body) : null;
}

function postgrestPath(table, parameters) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(parameters)) {
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item));
    } else if (value !== undefined && value !== null) search.set(key, String(value));
  }
  return `/${table}?${search}`;
}

async function listCandidates(startDate, endDate) {
  const rows = [];
  let lastId = null;
  while (true) {
    const parameters = {
      select: OPERATIONAL_SELECT,
      deleted_at: "is.null",
      status: "eq.answered",
      follow_up_status: "eq.open",
      inquiry_date: [
        `gte.${jstMidnightUtc(startDate)}`,
        `lt.${jstMidnightUtc(addUtcDays(endDate, 1))}`,
      ],
      order: "id.asc",
      limit: PAGE_SIZE,
    };
    if (lastId !== null) parameters.id = `gt.${lastId}`;
    const batch = await api(postgrestPath(TABLE, parameters));
    if (!Array.isArray(batch)) throw new Error("Supabase inquiry query did not return an array");
    if (batch.length === 0) break;
    for (const row of batch) {
      const id = requirePositiveInteger(row.id, "returned row id");
      if (lastId !== null && BigInt(id) <= BigInt(lastId)) throw new Error("Supabase pagination returned non-increasing inquiry IDs");
      lastId = id;
      rows.push(row);
    }
    if (batch.length < PAGE_SIZE) break;
  }
  return rows;
}

if (command === "preflight-send") {
  if (!explicitlyEnabled(environment, DB_WRITES_SWITCH)) {
    throw new Error(`${DB_WRITES_SWITCH}=true is required before sending`);
  }
  if (!explicitlyEnabled(environment, EXTERNAL_SEND_SWITCH)) {
    throw new Error(`${EXTERNAL_SEND_SWITCH}=true is required before sending`);
  }
  console.log("Follow-up send preflight passed: external sending and database status writes are explicitly enabled.");
} else if (command === "query") {
  if (!options.output) throw new Error("query requires --output FILE");
  const start = requireDate(options.start ?? todayInJst(-5), "start date");
  const end = requireDate(options.end ?? todayInJst(-2), "end date");
  if (start > end) throw new Error(`Invalid date range: ${start} is after ${end}`);
  const rows = await listCandidates(start, end);
  writePrivateJson(options.output, {
    generatedAt: new Date().toISOString(),
    timezone: "Asia/Tokyo",
    periodStart: start,
    periodEnd: end,
    workflowStatus: "answered",
    followUpStatus: "open",
    count: rows.length,
    records: rows.map(operationalRow),
  });
  console.log(`Saved ${rows.length} answered/open inquiries for ${start} through ${end} JST to ${options.output}`);
} else if (command === "get") {
  if (!options.id || !options.output) throw new Error("get requires --id ROW_ID --output FILE");
  const id = requirePositiveInteger(options.id, "row id");
  const rows = await api(postgrestPath(TABLE, {
    select: OPERATIONAL_SELECT,
    id: `eq.${id}`,
    deleted_at: "is.null",
    limit: 1,
  }));
  if (!Array.isArray(rows) || rows.length !== 1) throw new Error(`Active inquiry ${id} not found`);
  writePrivateJson(options.output, operationalRow(rows[0]));
  console.log(`Saved inquiry ${id} to ${options.output}`);
} else if (command === "batch-status") {
  if (!options.input) throw new Error("batch-status requires --input FILE");
  const rawActions = JSON.parse(fs.readFileSync(options.input, "utf8"));
  if (!Array.isArray(rawActions) || rawActions.length === 0) throw new Error("Status input must be a non-empty array");
  const dryRun = options["dry-run"] === true;
  const actions = rawActions.map((action) => validateAction(action, dryRun));
  if (new Set(actions.map((action) => action.id)).size !== actions.length) throw new Error("Status input contains duplicate inquiry IDs");
  if (dryRun) {
    console.log(`Dry run: validated ${actions.length} status updates; no rows changed.`);
  } else {
    if (!explicitlyEnabled(environment, DB_WRITES_SWITCH)) {
      throw new Error(`${DB_WRITES_SWITCH}=true is required for database writes`);
    }
    if (actions.some((action) => action.status === "followed_up") && !explicitlyEnabled(environment, EXTERNAL_SEND_SWITCH)) {
      throw new Error(`${EXTERNAL_SEND_SWITCH}=true is required before recording a sent follow-up`);
    }
    const now = new Date().toISOString();
    for (const action of actions) {
      const { filters, payload } = patchContract(action, now);
      const rows = await api(postgrestPath(TABLE, { select: "id,status,follow_up_status,follow_up_sent_at", ...filters }), {
        method: "PATCH",
        headers: { Prefer: "return=representation" },
        body: JSON.stringify(payload),
      });
      if (!Array.isArray(rows) || rows.length !== 1 || String(rows[0].id) !== action.id) {
        throw new Error(`Conditional update for inquiry ${action.id} changed ${Array.isArray(rows) ? rows.length : 0} rows`);
      }
    }
    console.log(`Updated ${actions.length} inquiry statuses. Run verify-status with the same input.`);
  }
} else if (command === "verify-status") {
  if (!options.input) throw new Error("verify-status requires --input FILE");
  const rawExpected = JSON.parse(fs.readFileSync(options.input, "utf8"));
  if (!Array.isArray(rawExpected) || rawExpected.length === 0) throw new Error("Status input must be a non-empty array");
  const expected = rawExpected.map((action) => validateAction(action, true));
  if (new Set(expected.map((action) => action.id)).size !== expected.length) throw new Error("Status input contains duplicate inquiry IDs");
  const results = [];
  for (const action of expected) {
    const rows = await api(postgrestPath(TABLE, {
      select: "id,status,follow_up_status,follow_up_sent_at",
      id: `eq.${action.id}`,
      deleted_at: "is.null",
      limit: 1,
    }));
    const row = Array.isArray(rows) ? rows[0] : null;
    const workflowStatus = row?.status ?? "not_found";
    const followUpStatus = row?.follow_up_status ?? "not_found";
    const actual = ["closed_won", "closed_lose"].includes(action.status) ? workflowStatus : followUpStatus;
    const timestampPresent = action.status !== "followed_up" || Boolean(row?.follow_up_sent_at);
    results.push({
      id: action.id,
      expected: action.status,
      workflowStatus,
      followUpStatus,
      timestampPresent,
      verified: actual === action.status && timestampPresent,
    });
  }
  const report = {
    checkedAt: new Date().toISOString(),
    allVerified: results.every((result) => result.verified),
    results,
  };
  if (options.output) writePrivateJson(options.output, report);
  console.log(`Verified ${results.filter((result) => result.verified).length}/${results.length} statuses.`);
  if (!report.allVerified) process.exitCode = 1;
} else {
  throw new Error(`Unknown command: ${command}`);
}
