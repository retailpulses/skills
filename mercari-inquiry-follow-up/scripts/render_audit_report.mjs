#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  console.error("Usage: node render_audit_report.mjs INPUT.json OUTPUT.md");
  process.exit(2);
}

const data = JSON.parse(fs.readFileSync(inputPath, "utf8"));
if (!Array.isArray(data.cases)) {
  throw new Error("Input must contain a cases array");
}

const rows = data.cases.map((item, index) => ({
  caseRef: `CASE-${String(index + 1).padStart(3, "0")}`,
  date: item.inquiryDate || "--",
  shop: item.shop || "--",
  gate: item.chronologyGate || "unknown",
  action: item.action || "not-recorded",
  disclaimer: item.disclaimerVerified ? "yes" : "no",
  supabase: item.statusVerified ? "yes" : "no",
  note: String(item.note || "").replace(/\|/g, "\\|"),
}));

const count = (predicate) => rows.filter(predicate).length;
const lines = [
  "# Mercari inquiry follow-up audit",
  "",
  `- Period (JST): ${data.periodStart || "--"} to ${data.periodEnd || "--"}`,
  `- Generated: ${data.generatedAt || new Date().toISOString()}`,
  `- Cases reviewed: ${rows.length}`,
  `- Follow-ups sent: ${count((row) => row.action.startsWith("sent"))}`,
  `- Corrective replies sent: ${count((row) => row.action === "corrective-reply")}`,
  `- Skipped without a new message or closed: ${count((row) => ["skipped", "closed-lose"].includes(row.action))}`,
  `- Supabase statuses verified: ${count((row) => row.supabase === "yes")}`,
  "",
  "The report intentionally omits customer names, shop IDs, conversation IDs, order IDs, and product codes.",
  "",
  "| Case | Inquiry date | Shop | Chronology gate | Action | Disclaimer verified | Supabase verified | Note |",
  "|---|---|---|---|---|---:|---:|---|",
  ...rows.map(
    (row) =>
      `| ${row.caseRef} | ${row.date} | ${row.shop} | ${row.gate} | ${row.action} | ${row.disclaimer} | ${row.supabase} | ${row.note} |`,
  ),
  "",
  "## Completion controls",
  "",
  `- Every sent message visibly verified: ${data.allSentMessagesVerified ? "yes" : "no"}`,
  `- Every terminal Supabase state verified: ${data.allStatusesVerified ? "yes" : "no"}`,
  `- Job-related browser windows closed: ${data.jobWindowsClosed ? "yes" : "no"}`,
  "",
];

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, lines.join("\n"), "utf8");
