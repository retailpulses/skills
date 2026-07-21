# Changelog

## 2.0.0 - 2026-07-21

- BREAKING: Repointed all scripts from `mercari_inquiries` to canonical `inquiries` table in Supabase.
- BREAKING: Follow-up status column is now `follow_up_status` (values: `open`, `followed_up`, `do_not_follow_up`).
- BREAKING: Workflow status column `status` uses canonical values: `received`, `followed_up`, `answered`, `closed_won`, `closed_lose`.
- BREAKING: `query` filters on `follow_up_status` (not `status`); date filters use `inquiry_date` (not `last_message_at`).
- BREAKING: `batch-status` sets `follow_up_status` as primary column; `status` is also set to `followed_up` when follow-up is sent.
- BREAKING: `redactRow` uses `shop_key`, `customer_nickname`, `inquiry_date`; removed `itemCode`.
- Added kill switches: `INQUIRY_FOLLOWUP_DB_WRITES_ENABLED` and `INQUIRY_EXTERNAL_SEND_ENABLED`.
- Added `deleted_at=is.null` filter to `query`, `get`, and `verify-status` (soft-delete awareness).
- Updated `verify-status` to check `follow_up_status` (follow-up) and `status` (terminal states) independently.
- Updated `build_audit_input.mjs` to query both `follow_up_status` and `status` from `inquiries` table.
- Updated `render_audit_report.mjs` terminology from Baserow to Supabase.
- Updated SKILL.md with canonical column reference table and kill switch policy.
- Removed all Baserow API paths, table IDs, and configuration references.

## 1.2.0 - 2026-06-20

- Added `baserow_inquiries.mjs` for direct Baserow schema discovery, default JST-window queries, targeted record reads, batch status writes, follow-up date writes, and post-write verification.
- Removed Inquiry Portal UI dependency from the standard workflow and restricted browser/Computer Use to Mercari actions without a working script or alternative.
- Changed audit state refresh and report terminology from portal verification to direct Baserow verification.

## 1.1.1 - 2026-06-20

- Added `build_audit_input.mjs` to refresh batch inquiry states and create compact report input without loading full inquiry records.
- Clarified that the purchase disclaimer may use a clear equivalent in the customer's language.

## 1.1.0 - 2026-06-20

- Added a mandatory semantic answer-completeness gate before any conversion follow-up.
- Added a browser-neutral compact DOM audit helper usable through Chrome or Edge page evaluation.
- The DOM audit helper recognizes both product-linked customer messages and later text-only customer replies.
- Added an anonymized case-level Markdown audit report generator.
- Required report generation and verification before browser-window cleanup and job completion.

## 1.0.0 - 2026-06-20

- Created from a recorded Mercari inquiry follow-up session.
- Captured answered-queue review, correct-shop Chrome profile handling, live order/stock checks, Japanese drafting, sending, and verification.
- Added safeguards for customer privacy, unsupported urgency, wrong-profile messages, and duplicate sends.
