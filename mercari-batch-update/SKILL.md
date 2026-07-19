---
name: mercari-batch-update
description: Batch update existing Mercari listings — price, title, description, and/or category ID — from a CSV file. Supports dry-run, pre-check verification, and batched API mutations with safety guardrails. Logs results to Supabase mercari_batch_update_log. Use when the user wants to bulk update Mercari product fields, change prices/titles/descriptions/categories across multiple listings, or run a controlled batch mutation against Mercari Shops.
---

# Mercari Batch Update

Batch update existing Mercari Shop listings from a CSV file. Supports **price**, **title**, **description**, and **category ID** — individually or in any combination.

## When To Use

- Bulk price changes across multiple existing listings
- Batch title or description updates
- Category ID corrections or assignments
- Any combination of the above fields in a single run

**Not for:** creating new listings (use `mercari-csv-listing`), image reordering (use `mercari-image-rearrangement`), or image URL backfill (not supported by batch mutation).

## Safety Model

This skill enforces a **validate → dry-run → apply** workflow. The `--confirm` flag acts as a hard gate: you cannot execute live mutations without it.

| Phase | What happens | Mutations? | Command |
|-------|-------------|:---:|---------|
| **validate** | Parse CSV, check columns, detect update types, check token availability, validate field values | No | Automatic |
| **dry-run** | Full pipeline including live SKU→product lookup and price pre-check. Logs exactly what would change per row. | No | `--dry-run` |
| **apply** | Execute `updateProducts` mutations in batches of 20 with rate limiting. Saves per-row results to Supabase. | **Yes** | `--confirm` |

### Guardrails

- `--confirm` is ALWAYS required for live mutations.
- Batches of 20 items with rate limiting.
- Full dry-run before any mutation.
- Results logged to Supabase `mercari_batch_update_log`.

## Credentials

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — for writing results to `mercari_batch_update_log`
- `MERCARI_SHOP1_TOKEN` through `MERCARI_SHOP4_TOKEN` — Mercari shop API tokens
- `BASEROW_TOKEN` (legacy) — no longer used

## Supabase Logging

After each batch update, results are written to `mercari_batch_update_log`:

| Field | Value |
|-------|-------|
| `listing_id` | Mercari product ID |
| `shop` | shop1/shop2/shop3/shop4 |
| `update_type` | price/title/description/category |
| `old_value` | Previous value |
| `new_value` | New value |
| `success` | true/false |
| `error_message` | Error detail if failed |

Domain: `product_catalog`, owned by `retailpulses/RPagentOS`. Use PostgREST for writes.

## CSV Format

See `references/csv-columns.md` for column specifications and field naming conventions.
