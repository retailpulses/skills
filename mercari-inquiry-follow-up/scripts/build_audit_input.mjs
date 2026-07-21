#!/usr/bin/env node
/** Build audit input from answered inquiry snapshot via Supabase PostgREST.

Target: inquiries table (domain: inquiry_management, owner: retailpulses/inquiry-automation).
Canonical schema defined in supabase/migrations/20260721000000_create_inquiry_management_core.sql.
*/

import fs from "node:fs";
import path from "node:path";

const [snapshotPath, caseIdsPath, overridesPath, outputPath] = process.argv.slice(2);
if (!snapshotPath || !caseIdsPath || !overridesPath || !outputPath) {
  console.error(
    "Usage: node build_audit_input.mjs ANSWERED_SNAPSHOT.json CASE_IDS.json OVERRIDES.json OUTPUT.json",
  );
  process.exit(2);
}

const snapshot = JSON.parse(fs.readFileSync(snapshotPath, "utf8"));
const ids = JSON.parse(fs.readFileSync(caseIdsPath, "utf8"));
const overrides = JSON.parse(fs.readFileSync(overridesPath, "utf8"));
const snapshotRows = snapshot.records || snapshot.data;
if (!Array.isArray(snapshotRows) || !Array.isArray(ids)) {
  throw new Error("Snapshot must contain records[] (or legacy data[]) and case IDs must be an array");
}

function readEnv(filePath) {
  if (!fs.existsSync(filePath)) return {};
  return Object.fromEntries(
    fs.readFileSync(filePath, "utf8").split(/\r?\n/).flatMap((line) => {
      const match = line.trim().match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
      if (!match) return [];
      return [[match[1], match[2].trim().replace(/^(['"])(.*)\1$/, "$2")]];
    }),
  );
}

const envFile = process.env.SUPABASE_ENV_FILE || "/Users/user/Documents/Retailpulses/.env";
const fileEnv = readEnv(envFile);
const supabaseUrl = (process.env.SUPABASE_URL || fileEnv.SUPABASE_URL || "").replace(/\/$/, "");
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || fileEnv.SUPABASE_SERVICE_ROLE_KEY || "";
if (!supabaseUrl || !supabaseKey) throw new Error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");

const TABLE = "inquiries";
const BASE = `${supabaseUrl}/rest/v1`;

const statusById = new Map();
for (const id of ids) {
  const response = await fetch(`${BASE}/${TABLE}?id=eq.${id}&limit=1&select=id,follow_up_status,status`, {
    headers: {
      apikey: supabaseKey,
      Authorization: `Bearer ${supabaseKey}`,
      Accept: "application/json",
    },
  });
  if (!response.ok) throw new Error(`Row ${id} query failed: ${response.status}`);
  const data = await response.json();
  const row = Array.isArray(data) ? data[0] : data;
  statusById.set(id, {
    follow_up_status: row?.follow_up_status || "Unknown",
    status: row?.status || "Unknown",
  });
}

const snapshotById = new Map(snapshotRows.map((item) => [item.id, item]));
const inSet = (name, id) => (overrides._sets?.[name] || []).includes(id);
const groupedRule = (id) => {
  if (inSet("sentFollowedUp", id)) {
    return {
      chronologyGate: "passed",
      action: "sent",
      disclaimerVerified: true,
      expectedStatus: "followed_up",
      note: "Follow-up message and status verified.",
    };
  }
  if (inSet("sentButUnresolved", id)) {
    return {
      chronologyGate: "failed",
      action: "sent-needs-correction",
      disclaimerVerified: true,
      expectedStatus: "open",
      note: "Record restored to open because the prior customer question remains unresolved.",
    };
  }
  if (inSet("existingFollowUp", id)) {
    return {
      chronologyGate: "passed",
      action: "skipped",
      disclaimerVerified: false,
      expectedStatus: "followed_up",
      note: "An earlier proactive follow-up already existed; no duplicate was sent.",
    };
  }
  if (inSet("sentClosedLose", id)) {
    return {
      chronologyGate: "passed",
      action: "sent-then-closed-lose",
      disclaimerVerified: true,
      expectedStatus: "closed_lose",
      note: "Follow-up was sent and verified; a later customer response confirmed no conversion.",
    };
  }
  if (inSet("closedLose", id)) {
    return {
      chronologyGate: "special-concern",
      action: "closed-lose",
      disclaimerVerified: false,
      expectedStatus: "closed_lose",
      note: "No conversion follow-up sent; terminal non-conversion state verified.",
    };
  }
  if (inSet("unresolvedAnswered", id)) {
    return {
      chronologyGate: "failed",
      action: "skipped",
      disclaimerVerified: false,
      expectedStatus: "open",
      note: "Conversion follow-up withheld because a customer question remains unresolved or contradictory.",
    };
  }
  return {};
};
const cases = ids
  .map((id) => {
    const item = snapshotById.get(id);
    if (!item) throw new Error(`Case ${id} is missing from snapshot`);
    const rule = { ...groupedRule(id), ...(overrides[String(id)] || {}) };
    const dbStatus = statusById.get(id) || { status: "Not found", follow_up_status: "Not found" };
    // For terminal workflow states, verify against inquiries.status;
    // for follow-up lifecycle states, verify against follow_up_status.
    const expected = rule.expectedStatus;
    const actualForComparison = (["closed_lose", "closed_won"].includes(expected))
      ? dbStatus.status
      : dbStatus.follow_up_status;
    return {
      inquiryDate: new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Tokyo",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(new Date(item.inquiryDate || item.last_message_at)),
      shop: item.shop || item.account?.label || item.account || "--",
      chronologyGate: rule.chronologyGate || "reviewed",
      action: rule.action || "not-recorded",
      disclaimerVerified: Boolean(rule.disclaimerVerified),
      statusVerified: actualForComparison === expected,
      note: rule.note || dbStatus.follow_up_status || dbStatus.status || "Not found",
    };
  })
  .sort((a, b) => a.inquiryDate.localeCompare(b.inquiryDate) || a.shop.localeCompare(b.shop));

const output = {
  periodStart: overrides._meta?.periodStart || "--",
  periodEnd: overrides._meta?.periodEnd || "--",
  generatedAt: new Date().toISOString(),
  allSentMessagesVerified: Boolean(overrides._meta?.allSentMessagesVerified),
  allStatusesVerified: cases.every((item) => item.statusVerified),
  jobWindowsClosed: Boolean(overrides._meta?.jobWindowsClosed),
  cases,
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");
