#!/usr/bin/env node

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

const fileEnv = readEnv(process.env.BASEROW_ENV_FILE || "/Users/user/Documents/Retailpulses/.env");
const token = process.env.BASEROW_TOKEN || process.env.BASEROW_API_TOKEN || fileEnv.BASEROW_TOKEN || fileEnv.BASEROW_API_TOKEN;
const baseUrl = (process.env.BASEROW_BASE_URL || fileEnv.BASEROW_BASE_URL || "https://api.baserow.io").replace(/\/$/, "");
const tableId = process.env.BASEROW_INQUIRIES_TABLE_ID || fileEnv.BASEROW_INQUIRIES_TABLE_ID || "886975";
if (!token) throw new Error("Missing BASEROW_TOKEN");

const statusById = new Map();
for (const id of ids) {
  const response = await fetch(`${baseUrl}/api/database/rows/table/${tableId}/${id}/?user_field_names=true`, {
    headers: { Authorization: `Token ${token}` },
  });
  if (!response.ok) throw new Error(`Baserow row ${id} query failed: ${response.status}`);
  const row = await response.json();
  statusById.set(id, row.Status?.value || row.Status?.label || row.Status || "Unknown");
}

const snapshotById = new Map(snapshotRows.map((item) => [item.id, item]));
const inSet = (name, id) => (overrides._sets?.[name] || []).includes(id);
const groupedRule = (id) => {
  if (inSet("sentFollowedUp", id)) {
    return {
      chronologyGate: "passed",
      action: "sent",
      disclaimerVerified: true,
      expectedBaserowStatus: "Followed-up",
      note: "Follow-up message and Baserow status verified.",
    };
  }
  if (inSet("sentButUnresolved", id)) {
    return {
      chronologyGate: "failed",
      action: "sent-needs-correction",
      disclaimerVerified: true,
      expectedBaserowStatus: "Answered",
      note: "Record restored to Answered because the prior customer question remains unresolved.",
    };
  }
  if (inSet("existingFollowUp", id)) {
    return {
      chronologyGate: "passed",
      action: "skipped",
      disclaimerVerified: false,
      expectedBaserowStatus: "Followed-up",
      note: "An earlier proactive follow-up already existed; no duplicate was sent.",
    };
  }
  if (inSet("sentClosedLose", id)) {
    return {
      chronologyGate: "passed",
      action: "sent-then-closed-lose",
      disclaimerVerified: true,
      expectedBaserowStatus: "Closed Lose",
      note: "Follow-up was sent and verified; a later customer response confirmed no conversion.",
    };
  }
  if (inSet("closedLose", id)) {
    return {
      chronologyGate: "special-concern",
      action: "closed-lose",
      disclaimerVerified: false,
      expectedBaserowStatus: "Closed Lose",
      note: "No conversion follow-up sent; terminal non-conversion state verified.",
    };
  }
  if (inSet("unresolvedAnswered", id)) {
    return {
      chronologyGate: "failed",
      action: "skipped",
      disclaimerVerified: false,
      expectedBaserowStatus: "Answered",
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
    const status = statusById.get(id) || "Not found in first 100 results";
    return {
      inquiryDate: new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Tokyo",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(new Date(item.inquiryDate)),
      shop: item.account?.label || item.account || item.Account?.value || "--",
      chronologyGate: rule.chronologyGate || "reviewed",
      action: rule.action || "not-recorded",
      disclaimerVerified: Boolean(rule.disclaimerVerified),
      baserowStatusVerified: status === rule.expectedBaserowStatus,
      note: rule.note || status,
    };
  })
  .sort((a, b) => a.inquiryDate.localeCompare(b.inquiryDate) || a.shop.localeCompare(b.shop));

const output = {
  periodStart: overrides._meta?.periodStart || "--",
  periodEnd: overrides._meta?.periodEnd || "--",
  generatedAt: new Date().toISOString(),
  allSentMessagesVerified: Boolean(overrides._meta?.allSentMessagesVerified),
  allBaserowStatesVerified: cases.every((item) => item.baserowStatusVerified),
  jobWindowsClosed: Boolean(overrides._meta?.jobWindowsClosed),
  cases,
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");
