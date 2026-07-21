#!/usr/bin/env node
/** Query and update Mercari inquiry records via Supabase PostgREST.

Target: inquiries table (domain: inquiry_management, owner: retailpulses/inquiry-automation).
Canonical schema defined in supabase/migrations/20260721000000_create_inquiry_management_core.sql.
*/

import fs from "node:fs";
import path from "node:path";

const DEFAULT_ENV_FILE = "/Users/user/Documents/Retailpulses/.env";
const PAGE_SIZE = 200;

// ---------------------------------------------------------------------------
// Kill switch keys (read from environment)
// ---------------------------------------------------------------------------
const KW_DB_WRITES = "INQUIRY_FOLLOWUP_DB_WRITES_ENABLED";
const KW_EXTERNAL_SEND = "INQUIRY_EXTERNAL_SEND_ENABLED";

function isKillSwitchEnabled(key, env = process.env) {
  const val = env[key];
  // Absent or "true"/"1"/"yes" → enabled;  "false"/"0"/"no" → disabled
  if (val === undefined || val === null) return true;
  const normalized = String(val).trim().toLowerCase();
  return !["false", "0", "no", ""].includes(normalized);
}

function parseArgs(argv) {
  const command = argv[0];
  const options = {};
  for (let i = 1; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) throw new Error(`Unexpected argument: ${arg}`);
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) options[key] = true;
    else {
      options[key] = next;
      i += 1;
    }
  }
  return { command, options };
}

function loadEnvFile(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return {};
  const result = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    let value = match[2].trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    result[match[1]] = value;
  }
  return result;
}

function jstDate(offsetDays = 0) {
  const now = new Date();
  const jst = new Date(now.getTime() + 9 * 60 * 60 * 1000 + offsetDays * 86400000);
  return jst.toISOString().slice(0, 10);
}

function dateInJst(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function selectValue(value) {
  if (value && typeof value === "object") return value.value ?? value.label ?? value.id ?? null;
  return value ?? null;
}

function redactRow(row) {
  return {
    id: row.id,
    inquiryDate: dateInJst(row.inquiry_date),
    followUpStatus: row.follow_up_status,
    status: row.status,
    shop: row.shop_key,
    customerName: row.customer_nickname,
    notes: row.notes,
    followUpSentAt: row.follow_up_sent_at,
    followUpDate: row.follow_up_sent_at,
  };
}

// ---------------------------------------------------------------------------
// CLI parsing
// ---------------------------------------------------------------------------

const { command, options } = parseArgs(process.argv.slice(2));
if (!command || options.help) {
  console.log(`Usage:
  node supabase_inquiries.mjs query [--status <follow_up_status>] [--start YYYY-MM-DD] [--end YYYY-MM-DD] --output FILE
  node supabase_inquiries.mjs get --id ROW_ID --output FILE
  node supabase_inquiries.mjs batch-status --input FILE [--dry-run]
  node supabase_inquiries.mjs verify-status --input FILE [--output FILE]

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  INQUIRY_FOLLOWUP_DB_WRITES_ENABLED  (default: true; set to false to skip DB writes)
  INQUIRY_EXTERNAL_SEND_ENABLED       (default: true; set to false to skip external sends)

Target: public.inquiries table.
The default query window is N-5 through N-2 inclusive in Asia/Tokyo.
Follow-up status values: open, followed_up, do_not_follow_up.`);
  process.exit(command ? 0 : 2);
}

const envFile = options["env-file"] || process.env.SUPABASE_ENV_FILE || DEFAULT_ENV_FILE;
const fileEnv = loadEnvFile(envFile);
// Merge so kill-switch lookups check process.env first, then file env
const mergedEnv = { ...fileEnv, ...process.env };

const supabaseUrl = (mergedEnv.SUPABASE_URL || "").replace(/\/$/, "");
const supabaseKey = mergedEnv.SUPABASE_SERVICE_ROLE_KEY || "";
if (!supabaseUrl || !supabaseKey) throw new Error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");

const TABLE = "inquiries";
const BASE = `${supabaseUrl}/rest/v1`;

function headers() {
  return {
    apikey: supabaseKey,
    Authorization: `Bearer ${supabaseKey}`,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

async function api(path, init = {}) {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...headers(), ...(init.headers || {}) },
  });
  if (!response.ok) {
    const body = (await response.text()).slice(0, 800);
    throw new Error(`Supabase ${response.status} ${response.statusText}: ${body}`);
  }
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  return JSON.parse(text);
}

async function listRows(followUpStatus, startDate, endDate) {
  const rows = [];
  let offset = 0;
  while (true) {
    let filter = "";
    const filters = [];
    filters.push("deleted_at=is.null");
    if (followUpStatus) filters.push(`follow_up_status=eq.${encodeURIComponent(followUpStatus)}`);
    if (startDate) filters.push(`inquiry_date=gte.${encodeURIComponent(startDate)}`);
    if (endDate) filters.push(`inquiry_date=lte.${encodeURIComponent(endDate)}`);
    if (filters.length) filter = "&" + filters.join("&");

    const path = `/${TABLE}?select=*&limit=${PAGE_SIZE}&offset=${offset}${filter}`;
    const batch = await api(path);
    if (!batch || !batch.length) break;
    rows.push(...batch);
    if (batch.length < PAGE_SIZE) break;
    offset += PAGE_SIZE;
  }
  return rows;
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

if (command === "query") {
  if (!options.output) throw new Error("query requires --output FILE to keep customer data out of terminal output");
  const start = options.start || jstDate(-5);
  const end = options.end || jstDate(-2);
  const followUpStatus = options.status || "open";
  if (start > end) throw new Error(`Invalid date range: ${start} is after ${end}`);
  const rows = await listRows(followUpStatus, start, end);
  const output = {
    generatedAt: new Date().toISOString(),
    timezone: "Asia/Tokyo",
    periodStart: start,
    periodEnd: end,
    status: followUpStatus,
    count: rows.length,
    records: rows.map(redactRow),
  };
  writeJson(options.output, output);
  console.log(`Saved ${rows.length} ${followUpStatus} inquiries for ${start} through ${end} JST to ${options.output}`);
} else if (command === "get") {
  if (!options.id || !options.output) throw new Error("get requires --id ROW_ID --output FILE");
  const rows = await api(`/${TABLE}?id=eq.${Number(options.id)}&deleted_at=is.null&limit=1`);
  if (!rows || !rows.length) throw new Error(`Inquiry ${options.id} not found`);
  writeJson(options.output, redactRow(rows[0]));
  console.log(`Saved inquiry ${Number(options.id)} to ${options.output}`);
} else if (command === "batch-status") {
  if (!options.input) throw new Error("batch-status requires --input FILE");
  const actions = JSON.parse(fs.readFileSync(options.input, "utf8"));
  if (!Array.isArray(actions) || actions.length === 0) throw new Error("Status input must be a non-empty array");

  // ---- Kill switch: database writes ----
  const dbWritesEnabled = isKillSwitchEnabled(KW_DB_WRITES, mergedEnv);
  if (!dbWritesEnabled) {
    console.log(`Kill switch ${KW_DB_WRITES}=false: database writes disabled. Validated ${actions.length} status updates; no rows changed.`);
  }

  // ---- Kill switch: external send ----
  const extSendEnabled = isKillSwitchEnabled(KW_EXTERNAL_SEND, mergedEnv);
  if (!extSendEnabled) {
    const followedUpActions = actions.filter((a) => a.status === "followed_up");
    if (followedUpActions.length > 0) {
      console.log(`Kill switch ${KW_EXTERNAL_SEND}=false: ${followedUpActions.length} follow-up sends are blocked. Status update is still recorded.`);
    }
  }

  const now = new Date().toISOString();

  if (options["dry-run"]) {
    console.log(`Dry run: validated ${actions.length} status updates; no rows changed.`);
  } else if (dbWritesEnabled) {
    for (const action of actions) {
      // Map to canonical columns:
      //   follow_up_status — always set (primary)
      //   status          — set to "followed_up" when follow-up is sent
      //   follow_up_sent_at — set when follow_up_status becomes "followed_up"
      const payload = { follow_up_status: action.status };
      if (action.status === "followed_up") {
        payload.status = "followed_up";
        payload.follow_up_sent_at = action.followUpDate || now;
      }
      await api(`/${TABLE}?id=eq.${Number(action.id)}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
        headers: { Prefer: "return=representation" },
      });
    }
    console.log(`Updated ${actions.length} inquiry statuses. Run verify-status with the same input.`);
  } else {
    console.log(`Skipped writes: ${actions.length} status updates not applied (${KW_DB_WRITES}=false).`);
  }
} else if (command === "verify-status") {
  if (!options.input) throw new Error("verify-status requires --input FILE");
  const expected = JSON.parse(fs.readFileSync(options.input, "utf8"));
  if (!Array.isArray(expected) || expected.length === 0) throw new Error("Status input must be a non-empty array");
  const results = [];
  for (const action of expected) {
    const rows = await api(`/${TABLE}?id=eq.${Number(action.id)}&deleted_at=is.null&limit=1`);
    const row = rows?.[0];
    // Verify against follow_up_status by default; for terminal workflow states,
    // also check status column
    const actual = row?.follow_up_status ?? "unknown";
    const workflowStatus = row?.status ?? "unknown";
    const isTerminal = ["closed_lose", "closed_won"].includes(action.status);
    const actualForComparison = isTerminal ? workflowStatus : actual;
    const verified = actualForComparison === action.status;
    results.push({
      id: Number(action.id),
      expected: action.status,
      actual,
      workflowStatus,
      verified,
    });
  }
  const report = {
    checkedAt: new Date().toISOString(),
    allVerified: results.every((item) => item.verified),
    results,
  };
  if (options.output) writeJson(options.output, report);
  console.log(`Verified ${results.filter((item) => item.verified).length}/${results.length} statuses.`);
  if (!report.allVerified) process.exitCode = 1;
} else {
  throw new Error(`Unknown command: ${command}`);
}
