#!/usr/bin/env node
/** Build anonymized audit input and refresh canonical inquiry states in batches. */

import fs from "node:fs";
import path from "node:path";

const argv = process.argv.slice(2);
const [snapshotPath, caseIdsPath, overridesPath, outputPath] = argv.slice(0, 4);
if (!snapshotPath || !caseIdsPath || !overridesPath || !outputPath) {
  console.error("Usage: node build_audit_input.mjs SNAPSHOT.json CASE_IDS.json OVERRIDES.json OUTPUT.json [--env-file FILE]");
  process.exit(2);
}

let envFile = null;
for (let index = 4; index < argv.length; index += 1) {
  if (argv[index] !== "--env-file" || !argv[index + 1] || index + 2 !== argv.length) {
    throw new Error(`Unexpected argument: ${argv[index]}`);
  }
  envFile = argv[index + 1];
  index += 1;
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

function positiveId(value) {
  const normalized = String(value ?? "").trim();
  if (!/^[1-9][0-9]*$/.test(normalized)) throw new Error(`Invalid inquiry id: ${value}`);
  return normalized;
}

function writePrivateJson(filePath, value) {
  const resolved = path.resolve(filePath);
  fs.mkdirSync(path.dirname(resolved), { recursive: true, mode: 0o700 });
  fs.writeFileSync(resolved, `${JSON.stringify(value, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  fs.chmodSync(resolved, 0o600);
}

const snapshot = JSON.parse(fs.readFileSync(snapshotPath, "utf8"));
const rawIds = JSON.parse(fs.readFileSync(caseIdsPath, "utf8"));
const overrides = JSON.parse(fs.readFileSync(overridesPath, "utf8"));
const snapshotRows = snapshot.records ?? snapshot.data;
if (!Array.isArray(snapshotRows) || !Array.isArray(rawIds) || rawIds.length === 0) {
  throw new Error("Snapshot must contain records[] and case IDs must be a non-empty array");
}
const ids = rawIds.map(positiveId);
if (new Set(ids).size !== ids.length) throw new Error("Case IDs contain duplicates");

const fileEnv = loadEnvFile(envFile);
const environment = { ...fileEnv, ...process.env };
const supabaseUrl = String(environment.SUPABASE_URL ?? "").replace(/\/$/, "");
const supabaseKey = String(environment.SUPABASE_SERVICE_ROLE_KEY ?? "");
if (!supabaseUrl || !supabaseKey) throw new Error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
const baseUrl = `${supabaseUrl}/rest/v1`;

async function readStatusBatch(batch) {
  const search = new URLSearchParams({
    select: "id,follow_up_status,status,follow_up_sent_at",
    id: `in.(${batch.join(",")})`,
    deleted_at: "is.null",
    order: "id.asc",
  });
  const response = await fetch(`${baseUrl}/inquiries?${search}`, {
    headers: {
      apikey: supabaseKey,
      Authorization: `Bearer ${supabaseKey}`,
      Accept: "application/json",
    },
  });
  if (!response.ok) {
    const body = (await response.text()).slice(0, 800);
    throw new Error(`Supabase status query failed (${response.status}): ${body}`);
  }
  const rows = await response.json();
  if (!Array.isArray(rows)) throw new Error("Supabase status query did not return an array");
  return rows;
}

const statusById = new Map();
for (let index = 0; index < ids.length; index += 100) {
  const batch = ids.slice(index, index + 100);
  for (const row of await readStatusBatch(batch)) {
    const id = positiveId(row.id);
    if (!batch.includes(id)) throw new Error(`Supabase returned unexpected inquiry id ${id}`);
    statusById.set(id, {
      followUpStatus: row.follow_up_status ?? "unknown",
      workflowStatus: row.status ?? "unknown",
      followUpSentAt: row.follow_up_sent_at ?? null,
    });
  }
}

const snapshotById = new Map(snapshotRows.map((item) => [positiveId(item.id), item]));
const normalizedSet = (name) => new Set((overrides._sets?.[name] ?? []).map(positiveId));
const sets = {
  sentFollowedUp: normalizedSet("sentFollowedUp"),
  sentButUnresolved: normalizedSet("sentButUnresolved"),
  existingFollowUp: normalizedSet("existingFollowUp"),
  sentClosedLose: normalizedSet("sentClosedLose"),
  closedLose: normalizedSet("closedLose"),
  unresolvedAnswered: normalizedSet("unresolvedAnswered"),
};

function groupedRule(id) {
  if (sets.sentFollowedUp.has(id)) return {
    chronologyGate: "passed",
    action: "sent",
    disclaimerVerified: true,
    expectedStatus: "followed_up",
    note: "Follow-up message and status verified.",
  };
  if (sets.sentButUnresolved.has(id)) return {
    chronologyGate: "failed",
    action: "sent-needs-correction",
    disclaimerVerified: true,
    expectedStatus: "open",
    note: "Record remains open because the prior customer question requires correction.",
  };
  if (sets.existingFollowUp.has(id)) return {
    chronologyGate: "passed",
    action: "skipped",
    disclaimerVerified: false,
    expectedStatus: "followed_up",
    note: "An earlier proactive follow-up already existed; no duplicate was sent.",
  };
  if (sets.sentClosedLose.has(id)) return {
    chronologyGate: "passed",
    action: "sent-then-closed-lose",
    disclaimerVerified: true,
    expectedStatus: "closed_lose",
    note: "Follow-up was sent and verified; a later response confirmed no conversion.",
  };
  if (sets.closedLose.has(id)) return {
    chronologyGate: "special-concern",
    action: "closed-lose",
    disclaimerVerified: false,
    expectedStatus: "closed_lose",
    note: "No conversion follow-up sent; terminal non-conversion state verified.",
  };
  if (sets.unresolvedAnswered.has(id)) return {
    chronologyGate: "failed",
    action: "skipped",
    disclaimerVerified: false,
    expectedStatus: "open",
    note: "Follow-up withheld because a customer question remains unresolved or contradictory.",
  };
  return {};
}

function jstDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error(`Invalid inquiry date in snapshot: ${value}`);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

const cases = ids.map((id) => {
  const item = snapshotById.get(id);
  if (!item) throw new Error(`Case ${id} is missing from snapshot`);
  const rule = { ...groupedRule(id), ...(overrides[id] ?? {}) };
  const database = statusById.get(id) ?? {
    followUpStatus: "not_found",
    workflowStatus: "not_found",
    followUpSentAt: null,
  };
  const expected = rule.expectedStatus;
  const actual = ["closed_lose", "closed_won"].includes(expected)
    ? database.workflowStatus
    : database.followUpStatus;
  const timestampVerified = expected !== "followed_up" || Boolean(database.followUpSentAt);
  return {
    inquiryDate: jstDate(item.inquiryDate ?? item.inquiry_date),
    shop: item.shop ?? "--",
    chronologyGate: rule.chronologyGate ?? "reviewed",
    action: rule.action ?? "not-recorded",
    disclaimerVerified: Boolean(rule.disclaimerVerified),
    statusVerified: Boolean(expected) && actual === expected && timestampVerified,
    note: rule.note ?? "No audit disposition recorded.",
  };
}).sort((left, right) => left.inquiryDate.localeCompare(right.inquiryDate) || left.shop.localeCompare(right.shop));

writePrivateJson(outputPath, {
  periodStart: overrides._meta?.periodStart ?? "--",
  periodEnd: overrides._meta?.periodEnd ?? "--",
  generatedAt: new Date().toISOString(),
  allSentMessagesVerified: overrides._meta?.allSentMessagesVerified === true,
  allStatusesVerified: cases.every((item) => item.statusVerified),
  jobWindowsClosed: overrides._meta?.jobWindowsClosed === true,
  cases,
});
