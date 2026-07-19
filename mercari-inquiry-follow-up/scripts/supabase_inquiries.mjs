#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

// TODO(2026-07-18): Migrate from Baserow API to Supabase PostgREST.
// Update DEFAULT_BASE_URL to SUPABASE_URL + /rest/v1/mercari_inquiries.
// See docs/BASEROW_TO_SUPABASE_MIGRATION.md for the migration plan.
const DEFAULT_BASE_URL = "https://api.baserow.io";  // DEPRECATED: migrate to Supabase
const DEFAULT_TABLE_ID = "886975";  // DEPRECATED: use mercari_inquiries table
const DEFAULT_ENV_FILE = "/Users/user/Documents/Retailpulses/.env";
const PAGE_SIZE = 200;

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
    inquiryDate: row["Inquiry Date"],
    status: selectValue(row.Status),
    account: selectValue(row.Account),
    inquiryType: selectValue(row["Inquiry Type"]),
    url: row.URL,
    productName: row["Product Name"],
    itemCode: row["Item code"],
    units: row.Units,
    quantityAvailable: row["Qty Available"],
    lastCustomerMessage: row["Last Custom Message"],
    messageLog: row["Message log"],
    inquiryBody: row["Inquiry body"],
    replyStrategy: row["Reply strategy"],
    draftReply: row["Draft reply"],
    followUpStrategy: row["Follow-up strategy"],
    followUpMessage: row["Follow-up msg"],
    followUpDate: row["Follow-up Date"],
    orderId: row.OrderID,
    orderDate: row["Order Date"],
  };
}

const { command, options } = parseArgs(process.argv.slice(2));
if (!command || options.help) {
  console.log(`Usage:
  node baserow_inquiries.mjs schema [--output FILE]
  node baserow_inquiries.mjs query [--status Answered] [--start YYYY-MM-DD] [--end YYYY-MM-DD] --output FILE
  node baserow_inquiries.mjs get --id ROW_ID --output FILE
  node baserow_inquiries.mjs batch-status --input FILE [--dry-run]
  node baserow_inquiries.mjs verify-status --input FILE [--output FILE]

Environment: BASEROW_TOKEN, BASEROW_BASE_URL, BASEROW_INQUIRIES_TABLE_ID.
The default query window is N-5 through N-2 inclusive in Asia/Tokyo.`);
  process.exit(command ? 0 : 2);
}

const envFile = options["env-file"] || process.env.BASEROW_ENV_FILE || DEFAULT_ENV_FILE;
const fileEnv = loadEnvFile(envFile);
const token = process.env.BASEROW_TOKEN || process.env.BASEROW_API_TOKEN || fileEnv.BASEROW_TOKEN || fileEnv.BASEROW_API_TOKEN;
const baseUrl = (process.env.BASEROW_BASE_URL || fileEnv.BASEROW_BASE_URL || DEFAULT_BASE_URL).replace(/\/$/, "");
const tableId = process.env.BASEROW_INQUIRIES_TABLE_ID || fileEnv.BASEROW_INQUIRIES_TABLE_ID || DEFAULT_TABLE_ID;
if (!token) throw new Error("Missing BASEROW_TOKEN");

async function api(relativeUrl, init = {}) {
  const response = await fetch(`${baseUrl}${relativeUrl}`, {
    ...init,
    headers: {
      Authorization: `Token ${token}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (!response.ok) {
    const body = (await response.text()).slice(0, 800);
    throw new Error(`Baserow ${response.status} ${response.statusText}: ${body}`);
  }
  return response.status === 204 ? null : response.json();
}

async function schema() {
  return api(`/api/database/fields/table/${tableId}/`);
}

function requiredField(fields, name) {
  const field = fields.find((item) => item.name === name);
  if (!field) throw new Error(`Required Baserow field is missing: ${name}`);
  return field;
}

function selectOption(fields, fieldName, value) {
  const field = requiredField(fields, fieldName);
  const option = (field.select_options || []).find((item) => item.value === value);
  if (!option) throw new Error(`Unknown ${fieldName} option: ${value}`);
  return option;
}

async function listRows(status) {
  const fields = await schema();
  const statusOption = status ? selectOption(fields, "Status", status) : null;
  const rows = [];
  let page = 1;
  while (true) {
    const params = new URLSearchParams({ user_field_names: "true", size: String(PAGE_SIZE), page: String(page) });
    if (statusOption) params.set(`filter__field_${requiredField(fields, "Status").id}__single_select_equal`, String(statusOption.id));
    const payload = await api(`/api/database/rows/table/${tableId}/?${params}`);
    rows.push(...payload.results);
    if (!payload.next) break;
    page += 1;
  }
  return rows;
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

if (command === "schema") {
  const fields = await schema();
  const safe = fields.map(({ id, name, type, select_options: selectOptions }) => ({
    id,
    name,
    type,
    options: selectOptions?.map(({ id: optionId, value }) => ({ id: optionId, value })),
  }));
  if (options.output) writeJson(options.output, safe);
  else console.log(JSON.stringify(safe, null, 2));
} else if (command === "query") {
  if (!options.output) throw new Error("query requires --output FILE to keep customer data out of terminal output");
  const start = options.start || jstDate(-5);
  const end = options.end || jstDate(-2);
  const status = options.status || "Answered";
  if (start > end) throw new Error(`Invalid date range: ${start} is after ${end}`);
  const rows = (await listRows(status)).filter((row) => {
    const date = dateInJst(row["Inquiry Date"]);
    return date && date >= start && date <= end;
  });
  const output = {
    generatedAt: new Date().toISOString(),
    timezone: "Asia/Tokyo",
    periodStart: start,
    periodEnd: end,
    status,
    count: rows.length,
    records: rows.map(redactRow),
  };
  writeJson(options.output, output);
  console.log(`Saved ${rows.length} ${status} inquiries for ${start} through ${end} JST to ${options.output}`);
} else if (command === "get") {
  if (!options.id || !options.output) throw new Error("get requires --id ROW_ID --output FILE");
  const row = await api(`/api/database/rows/table/${tableId}/${Number(options.id)}/?user_field_names=true`);
  writeJson(options.output, redactRow(row));
  console.log(`Saved inquiry ${Number(options.id)} to ${options.output}`);
} else if (command === "batch-status") {
  if (!options.input) throw new Error("batch-status requires --input FILE");
  const actions = JSON.parse(fs.readFileSync(options.input, "utf8"));
  if (!Array.isArray(actions) || actions.length === 0) throw new Error("Status input must be a non-empty array");
  const fields = await schema();
  const followUpField = fields.find((field) => field.name === "Follow-up Date");
  const now = new Date().toISOString();
  const items = actions.map((action) => {
    if (!Number.isInteger(Number(action.id))) throw new Error(`Invalid row id: ${action.id}`);
    const statusOption = selectOption(fields, "Status", action.status);
    const item = { id: Number(action.id), Status: statusOption.id };
    if (action.status === "Followed-up" && followUpField) item["Follow-up Date"] = action.followUpDate || now;
    return item;
  });
  if (options["dry-run"]) {
    console.log(`Dry run: validated ${items.length} status updates; no Baserow rows changed.`);
  } else {
    for (let i = 0; i < items.length; i += 100) {
      await api(`/api/database/rows/table/${tableId}/batch/?user_field_names=true`, {
        method: "PATCH",
        body: JSON.stringify({ items: items.slice(i, i + 100) }),
      });
    }
    console.log(`Updated ${items.length} Baserow inquiry statuses. Run verify-status with the same input.`);
  }
} else if (command === "verify-status") {
  if (!options.input) throw new Error("verify-status requires --input FILE");
  const expected = JSON.parse(fs.readFileSync(options.input, "utf8"));
  if (!Array.isArray(expected) || expected.length === 0) throw new Error("Status input must be a non-empty array");
  const results = [];
  for (const action of expected) {
    const row = await api(`/api/database/rows/table/${tableId}/${Number(action.id)}/?user_field_names=true`);
    const actual = selectValue(row.Status);
    results.push({ id: Number(action.id), expected: action.status, actual, verified: actual === action.status });
  }
  const report = { checkedAt: new Date().toISOString(), allVerified: results.every((item) => item.verified), results };
  if (options.output) writeJson(options.output, report);
  console.log(`Verified ${results.filter((item) => item.verified).length}/${results.length} Baserow statuses.`);
  if (!report.allVerified) process.exitCode = 1;
} else {
  throw new Error(`Unknown command: ${command}`);
}
