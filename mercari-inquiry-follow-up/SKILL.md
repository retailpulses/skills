---
name: mercari-inquiry-follow-up
description: Query and update canonical Mercari inquiry records through Supabase PostgREST, review answered conversations, and send proactive Japanese follow-ups from the correct logged-in Mercari shop profile. Use when the user asks to follow up Mercari inquiries, re-contact prospective buyers, check whether a customer still plans to purchase, confirm stock before messaging, or promote a current time sale without making unsupported claims.
---

# Mercari Inquiry Follow-up

Turn previously answered Mercari Shops inquiries into careful, context-aware follow-ups that prioritize conversion while protecting against purchase-status uncertainty.

## Data source

Use the canonical Supabase `public.inquiries` table in the `inquiry_management` governance domain, owned by `retailpulses/inquiry-automation`. This skill has no fallback operational datastore.

Follow-up candidates must satisfy all three conditions: `status=answered`, `follow_up_status=open`, and `deleted_at IS NULL`. The CLI also reads linked product snapshots from `public.inquiry_product_links`.

## Operating policy

- Prioritize conversion: a possible or confirmed prior purchase does not by itself block a polite follow-up.
- Unless the user specifies another range, process inquiries dated from `N-5` through `N-2`, inclusive, where `N` is today's date in Japan Standard Time (`Asia/Tokyo`).
- Every follow-up must include the standard already-purchased disclaimer in this skill, or a clear semantic equivalent in the customer's language.
- A request to follow up, re-contact, or send messages authorizes sending after the checks below. Do not pause for a separate confirmation unless there is a special concern.
- Special concerns include an unclear shop/profile mapping, a conversation mismatch, sensitive or hostile content, an unsupported factual claim that cannot be removed, or any other condition that could cause material customer harm. Purchase-status uncertainty alone is not a special concern when the disclaimer is included.
- Supabase inquiry discovery, record reads, draft/action fields, status writes, and post-write verification must be performed by scripts through PostgREST. Do not use the Inquiry Portal UI for these operations.
- The job is not complete until every successfully sent inquiry is updated and verified directly in Supabase and every window used by browser or Computer Use for the job is closed.

## Requirements

- Use `scripts/supabase_inquiries.mjs` for all inquiry queries, reads, status writes, and status verification.
- Database writes are disabled unless `INQUIRY_FOLLOWUP_DB_WRITES_ENABLED=true` is explicitly set. Customer sending is disabled unless `INQUIRY_EXTERNAL_SEND_ENABLED=true` is explicitly set. Missing, empty, or any other value means disabled.
- Never mark an inquiry `followed_up` unless the matching message is visibly present in the Mercari conversation. The status action must contain `"sendConfirmed": true`; the CLI rejects the write otherwise.
- Supply credentials through `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. The scripts do not search default credential files. Use `--env-file FILE` only when an explicit local file is intended. `SUPABASE_REST_URL` may point at a disposable PostgREST root during local validation; hosted use derives `/rest/v1` from `SUPABASE_URL`.
- Use the user's existing logged-in Chrome or Edge profile only for Mercari operations that have no available script or API alternative. Shop authentication and profile state matter.
- Expect Mercari Shops seller pages at `https://mercari-shops.com/seller/shops/...`. The Inquiry Portal is an emergency fallback only when direct Supabase access is unavailable and the script failure cannot be repaired during the run.
- Do not expose customer names, shop IDs, conversation IDs, order IDs, or product codes in reports or reusable files.
- Sending is an external action. Draft and verify first; when the user's request asks to follow up, re-contact, or send, treat that request as authorization and proceed without reconfirming unless a special concern exists.
- Use `scripts/mercari_conversation_audit.js` through the active browser's page-evaluation API to extract a compact chronology record. The DOM-only script is browser-neutral and can be used with Chrome or Edge when the automation surface exposes page evaluation.

## Workflow

1. Run `node scripts/supabase_inquiries.mjs query --output WORK_QUEUE.json`. The script applies the inclusive `N-5` through `N-2` JST window as exact UTC bounds and selects only active `answered`/`open` candidates. Pass `--start` and `--end` only when the user specifies another range.
2. Read inquiry date, shop, URL, product, quantity, message log, latest customer message, draft/action fields, and current status from the private-mode work queue or with `node scripts/supabase_inquiries.mjs get --id ROW_ID --output ROW.json`. Do not open the Inquiry Portal for record reads. When Mercari UI inspection is necessary, run `scripts/mercari_conversation_audit.js` through page evaluation to reduce the conversation to compact JSON instead of repeatedly dumping full DOM snapshots.
3. Apply the mandatory answer-completeness gate before drafting:
   - Identify the latest customer-authored message that existed before any follow-up.
   - Identify the seller response that follows it.
   - Verify semantically that every question, request, and correction in the latest customer message was answered. A seller message existing after it is not sufficient evidence.
   - If the latest customer message is newer than the latest seller response, or the seller response is generic, evasive, incomplete, or answers a different question, do not send a conversion follow-up. Answer the unresolved inquiry first or leave the record in `answered` and report the special concern.
   - Preserve a compact audit result containing the role sequence, latest customer text, latest seller text, and the gate decision. Do not store private text in the final report.
4. Decide whether a follow-up is appropriate with conversion as the priority:
   - Follow up when the earlier reply answered a sales, shipping, bulk-purchase, availability, or delivery-timing question and the customer has not clearly declined.
   - A possible or confirmed purchase is not an automatic skip; keep the message useful and include the already-purchased disclaimer.
   - Skip if the customer clearly declined, a proactive follow-up was already sent, the product cannot be purchased, the conversation is hostile or sensitive, the message would be repetitive, or the correct shop/conversation cannot be verified.
5. Open the conversation link in the Chrome or Edge profile mapped to the inquiry's shop. Verify the Mercari shop and customer conversation match the Supabase record before composing anything.
6. Check purchase status when practical so the message can be better personalized, but do not let an inconclusive search block an otherwise safe conversion follow-up:
   - Open the shop's `注文` page.
   - Search by product management code, product name, variant name, or order number.
   - Include relevant statuses such as `発送済み` when the default filter would hide completed orders.
   - If a likely purchase is found, avoid language that assumes the customer has not purchased and rely on the standard disclaimer.
   - Confirm the exact product or variant remains available before inviting direct purchase or claiming stock.
   - Confirm any time sale or urgency claim from the live listing or a current API result. Never infer scarcity from an old note.
7. Draft the follow-up from the Supabase-sourced context and verified Mercari facts. If draft or strategy fields must be persisted, write them through the owner-approved server-side inquiry API; do not expose the service-role key to a browser or use the Inquiry Portal drafting UI.
8. Review the generated Japanese before copying it. The message should:
   - thank the customer for the earlier inquiry;
   - refer naturally to the unresolved question or buying timeline;
   - mention verified stock, direct-purchase availability, delivery context, or a live promotion only when relevant;
   - invite questions without pressuring the customer;
   - include `すでにご購入いただいている場合は、行き違いとなりましたことをご容赦いただき、本メッセージはご放念ください。`, or a clear semantic equivalent in the customer's language;
   - end with `ホムブリスカスタマーサポート`.
9. Copy the final draft, return to the matching Mercari conversation, paste into `返信を入力する`, and re-check the recipient, product/variant, quantities, dates, prices, stock, promotion claims, and answer-completeness gate.
10. Immediately before any send, run `node scripts/supabase_inquiries.mjs preflight-send`. Proceed only when it exits successfully. When the request authorizes follow-up sending and no special concern exists, click `送信` once without asking for another confirmation. Verify the new message appears in the matching conversation before changing any Supabase state.
11. Only after the sent message is visibly confirmed, append `{ "id": ROW_ID, "status": "followed_up", "sendConfirmed": true }` to the status action file. Run `node scripts/supabase_inquiries.mjs batch-status --input STATUS_ACTIONS.json`, then `node scripts/supabase_inquiries.mjs verify-status --input STATUS_ACTIONS.json --output STATUS_VERIFICATION.json`. The conditional write requires the row still to be active, `answered`, and `open`, and records `follow_up_sent_at`. If the write or verification fails, repair and retry only the Supabase operation without resending the Mercari message. A sent message with an unverified Supabase update remains incomplete.
12. Continue with the next eligible inquiry. Keep shop/profile context isolated between cases.
13. Build an anonymized machine-readable audit manifest and run `node scripts/render_audit_report.mjs INPUT.json OUTPUT.md`. For larger batches, use `node scripts/build_audit_input.mjs WORK_QUEUE.json CASE_IDS.json OVERRIDES.json INPUT.json`; it refreshes case states from Supabase in batches. The report must cover every in-scope inquiry and record inquiry date, shop label, chronology-gate result, action, disclaimer verification, Supabase verification, and a non-private note.
14. After all messages, Supabase updates, and the audit report are verified, close every browser or app window used for this job, including Mercari conversation, order, listing, and search windows. Delete temporary work queues when they are no longer required. Do not leave a job window open as a handoff.

## Message patterns

Use these as structures, not fixed scripts.

### Clarify need or delivery timing

```text
お問い合わせいただき、誠にありがとうございます。

先日ご案内した内容について、ご不明な点はございませんでしょうか。差し支えなければ、商品のご利用予定日をお知らせください。ご希望に沿ってご案内いたします。

すでにご購入いただいている場合は、行き違いとなりましたことをご容赦いただき、本メッセージはご放念ください。

何卒よろしくお願いいたします。

ホムブリスカスタマーサポート
```

### Verified stock or promotion follow-up

```text
お世話になっております。この度はお問い合わせいただき、誠にありがとうございます。

先日のお問い合わせについて、購入のご予定はお決まりでしょうか。現在、対象の【商品・種類】は在庫があり、直接ご購入いただけます。【確認済みの場合のみ：ただいまタイムセールを実施中です。】

ご不明な点がございましたら、お気軽にお問い合わせください。

すでにご購入いただいている場合は、行き違いとなりましたことをご容赦いただき、本メッセージはご放念ください。

ホムブリスカスタマーサポート
```

## Guardrails

- Do not send a follow-up based only on the card summary; read the conversation.
- Do not treat an `answered` database status or the mere presence of a seller message as proof that the customer's latest question was answered. The semantic answer-completeness gate is mandatory.
- Do not omit the already-purchased disclaimer, even when an order search finds no match; purchases can occur between checking and sending.
- Do not claim stock, last-unit status, sale pricing, delivery dates, or availability without a current check.
- Do not promise carrier delivery timing that the shop cannot control.
- Do not reuse text across customers without adapting the product, variant, and prior question.
- Do not message the wrong shop profile. If profile-to-shop mapping is unclear, stop before pasting or sending.
- Do not mark an inquiry `followed_up` in Supabase until its sent message is visibly confirmed in the matching Mercari conversation.
- Do not resend a message merely because a Supabase write or verification failed; retry only the database operation.
- Do not use Computer Use for inquiry queue selection, inquiry record reads, drafting/status fields, status changes, or status verification. These are script-only Supabase operations.
- Before any UI action, check whether the same action is available through the Supabase script or another existing API/script. Use browser automation only when no working script alternative exists.
- Do not close browser or Computer Use windows before sent-message and Supabase-status verification is complete.
- Avoid manipulative urgency. Mention a sale or limited inventory factually and only while it is live.
- Never include internal drafting notes such as `proactively follow-up` in the customer-facing message.

## Change log

- 2026-07-22: Migrated active inquiry reads and writes to canonical Supabase PostgREST with fail-closed workload controls and conditional status transitions.
- 2026-06-20: Added a mandatory semantic chronology gate, a Chrome/Edge-neutral compact DOM audit script, a status-aware batch manifest builder, and an anonymized auditable-report generator after a live-run execution deviation exposed that a database status alone is not sufficient evidence.
- 2026-06-20: Made conversion the primary objective, set the default scope to inclusive `N-5` through `N-2` in JST, made the already-purchased disclaimer mandatory, and removed separate send reconfirmation except for special concerns.
- 2026-06-20: Required a verified follow-up state after each send and closure of all browser/Computer Use job windows before completion.

## Completion report

Create and save a case-level anonymized Markdown report with `scripts/render_audit_report.mjs`, then report aggregate operational details in chat: inquiries reviewed, chronology gates passed/failed, messages sent, corrective replies, Supabase terminal states verified, cases skipped or closed, incomplete Supabase updates, and confirmation that all browser/Computer Use job windows were closed. Do not include private customer or order details.

## Example triggers

- "Follow up the answered Mercari inquiries."
- "Re-contact customers who asked about delivery but did not buy."
- "Check stock and send a polite Mercari follow-up."
- "Follow up inquiries while the item is on time sale."
