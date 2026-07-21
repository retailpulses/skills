# Changelog

## 2.0.0 - 2026-07-22

- Replaced the active inquiry datastore client with canonical Supabase PostgREST access to `public.inquiries` and `public.inquiry_product_links`.
- Restricted the default work queue to active inquiries whose workflow state is `answered` and follow-up state is `open`.
- Added fail-closed database-write and external-send controls, visible-send confirmation proof, and conditional zero-row-checked status transitions.
- Added exact JST-to-UTC query boundaries, deterministic keyset pagination, private-mode output files, batched audit state reads, and black-box local HTTP tests.
- Preserved the semantic answer-completeness gate, correct-shop verification, send verification, and anonymized completion report.
- Related to retailpulses/inquiry-automation#35.

## 1.2.0 - 2026-06-20

- Added `baserow_inquiries.mjs` for direct Baserow schema discovery, default JST-window queries, targeted record reads, batch status writes, follow-up date writes, and post-write verification.
- Removed Inquiry Portal UI dependency from the standard workflow and restricted browser/Computer Use to Mercari actions without a working script or API alternative.
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
