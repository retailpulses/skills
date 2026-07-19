---
name: mercari-inquiry-follow-up
description: Query and update Mercari inquiry records through Supabase PostgREST API, review answered conversations, and send proactive Japanese follow-ups from the correct logged-in Mercari shop profile. Use when the user asks to follow up Mercari inquiries, re-contact prospective buyers, check whether a customer still plans to purchase, confirm stock before messaging, or promote a current time sale without making unsupported claims.
---

# Mercari Inquiry Follow-up

Turn previously answered Mercari Shops inquiries into careful, context-aware follow-ups that prioritize conversion while protecting against purchase-status uncertainty.

## Data Source

Supabase `mercari_inquiries` table. Domain: `product_catalog`, owned by `retailpulses/RPagentOS`. Replaces Baserow table 886975.

## Operating policy

- Prioritize conversion: a possible or confirmed prior purchase does not by itself block a polite follow-up.
- Unless the user specifies another range, process inquiries dated from `N-5` through `N-2`, inclusive, where `N` is today's date in Japan Standard Time (`Asia/Tokyo`).
- Every follow-up must include the standard already-purchased disclaimer in this skill, or a clear semantic equivalent in the customer's language.
- A request to follow up, re-contact, or send messages authorizes sending after the checks below. Do not pause for a separate confirmation unless there is a special concern.
- Special concerns include an unclear shop/profile mapping, a conversation mismatch, sensitive or hostile content, an unsupported factual claim that cannot be removed, or any other condition that could cause material customer harm. Purchase-status uncertainty alone is not a special concern when the disclaimer is included.
- Supabase inquiry discovery, record reads, draft/action fields, status writes, and post-write verification must be performed by scripts through PostgREST API. Do not use the Inquiry Portal UI for these operations.
- The job is not complete until every successfully sent inquiry is updated and verified directly in Supabase and every window used by browser or Computer Use for the job is closed.

## Requirements

- Use `scripts/supabase_inquiries.mjs` for all inquiry queries, reads, status writes, and status verification against Supabase `mercari_inquiries` table.
- Use the user's existing logged-in Chrome or Edge profile only for Mercari operations that have no available script or API alternative. Shop authentication and profile state matter.
- Expect Mercari Shops seller pages at `https://mercari-shops.com/seller/shops/...`. The Inquiry Portal is an emergency fallback only when direct Supabase access is unavailable and the script failure cannot be repaired during the run.
- Do not expose customer names, shop IDs, conversation IDs, order IDs, or product codes in reports or reusable files.
- Sending is an external action. Draft and verify first; when the user's request asks to follow up, re-contact, or send, treat that request as authorization and proceed without reconfirming unless a special concern exists.
- Use `scripts/mercari_conversation_audit.js` through the active browser's page-evaluation API to extract a compact chronology record. The DOM-only script is browser-neutral and can be used with Chrome or Edge when the automation surface exposes page evaluation.

## Credentials

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — service_role key for reads/writes
- `BASEROW_TOKEN` (legacy) — no longer used
