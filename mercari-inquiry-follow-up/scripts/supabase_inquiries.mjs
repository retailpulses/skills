#!/usr/bin/env node
/** Query and update Mercari inquiry records via Supabase PostgREST.

Replaces Baserow API with Supabase PostgREST.
Target: mercari_inquiries table (domain: product_catalog, owner: retailpulses/RPagentOS).
*/

import fs from "node:fs";
import path from "node:path";

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
    inquiryDate: row.last_message_at,
    status: row.status,
    shop: row.shop,
    customerName: row.customer_name,
    itemCode: row.item_code,
    notes: row.notes,
    followUpSentAt: row.follow_up_sent_at,
    followUpDate: row.follow_up_sent_at,
  };
}

const { command, options } = parseArgs(process.argv.slice(2));
if (!command || options.help) {
  console.log(`Usage:
  node supabase_inquiries.mjs query [--status <status>] [--start YYYY-MM-DD] [--end YYYY-MM-DD] --output FILE
  node supabase_inquiries.mjs get --id ROW_ID --output FILE
  node supabase_inquiries.mjs batch-status --input FILE [--dry-run]
  node supabase_inquiries.mjs verify-status --input FILE [--output FILE]

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
The default query window is N-5 through N-2 inclusive in Asia/Tokyo.`);
  process.exit(command ? 0 : 2);
}

const envFile = options["env-file"] || process.env.SUPABASE_ENV_FILE || DEFAULT_ENV_FILE;
const fileEnv = loadEnvFile(envFile);
const supabaseUrl = (process.env.SUPABASE_URL || fileEnv.SUPABASE_URL || "").replace(/\/$/, "");
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || fileEnv.SUPABASE_SERVICE_ROLE_KEY || "";
if (!supabaseUrl || !supabaseKey) throw new Error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");

const TABLE = "mercari_inquiries";
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

async function listRows(status, startDate, endDate) {
  const rows = [];
  let offset = 0;
  while (true) {
    let filter = "";
    const filters = [];
    if (status) filters.push(`status=eq.${encodeURIComponent(status)}`);
    if (startDate) filters.push(`last_message_at=gte.${encodeURIComponent(startDate)}`);
    if (endDate) filters.push(`last_message_at=lte.${encodeURIComponent(endDate)}`);
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
  const status = options.status || "open";
  if (start > end) throw new Error(`Invalid date range: ${start} is after ${end}`);
  const rows = await listRows(status, start, end);
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
  const rows = await api(`/${TABLE}?id=eq.${Number(options.id)}&limit=1`);
  if (!rows || !rows.length) throw new Error(`Inquiry ${options.id} not found`);
  writeJson(options.output, redactRow(rows[0]));
  console.log(`Saved inquiry ${Number(options.id)} to ${options.output}`);
} else if (command === "batch-status") {
  if (!options.input) throw new Error("batch-status requires --input FILE");
  const actions = JSON.parse(fs.readFileSync(options.input, "utf8"));
  if (!Array.isArray(actions) || actions.length === 0) throw new Error("Status input must be a non-empty array");
  const now = new Date().toISOString();

  if (options["dry-run"]) {
    console.log(`Dry run: validated ${actions.length} status updates; no rows changed.`);
  } else {
    for (const action of actions) {
      const payload = { status: action.status };
      if (action.status === "Followed-up") payload.follow_up_sent_at = action.followUpDate || now;
      await api(`/${TABLE}?id=eq.${Number(action.id)}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
        headers: { Prefer: "return=representation" },
      });
    }
    console.log(`Updated ${actions.length} inquiry statuses. Run verify-status with the same input.`);
  }
} else if (command === "verify-status") {
  if (!options.input) throw new Error("verify-status requires --input FILE");
  const expected = JSON.parse(fs.readFileSync(options.input, "utf8"));
  if (!Array.isArray(expected) || expected.length === 0) throw new Error("Status input must be a non-empty array");
  const results = [];
  for (const action of expected) {
    const rows = await api(`/${TABLE}?id=eq.${Number(action.id)}&limit=1`);
    const actual = rows?.[0]?.status ?? "unknown";
    results.push({ id: Number(action.id), expected: action.status, actual, verified: actual === action.status });
  }
  const report = { checkedAt: new Date().toISOString(), allVerified: results.every((item) => item.verified), results };
  if (options.output) writeJson(options.output, report);
  console.log(`Verified ${results.filter((item) => item.verified).length}/${results.length} statuses.`);
  if (!report.allVerified) process.exitCode = 1;
} else {
  throw new Error(`Unknown command: ${command}`);
}
