---
name: amazon-inventory-flatfile
description: Update Amazon listing inventory in Supabase, generate Amazon Price and Quantity flat files from the official template, and summarize Amazon processing summaries into execution reports. Use when the user asks to sync Amazon listings inventory from product_variants, create an Amazon inventory upload file, inspect a `PriceAndQuantity.xlsm` template, or review an Amazon processing summary after upload.
---

# Amazon Inventory Flatfile

## Overview

Execute the Amazon inventory workflow in three steps:

1. Sync `amazon_listings` inventory from `product_variants` in Supabase.
2. Generate a valid Amazon inventory upload file from the official `PriceAndQuantity.xlsm` template.
3. If the user provides a processing summary, generate an execution report in Markdown.

Use the scripts in `scripts/` for repeatable work. Read [references/workflow.md](references/workflow.md) when you need the verified defaults, matching rules, and failure modes.

## Data Source

Supabase `amazon_listings` table and `baserow_886994_compat_vw` (joins `product_variants` + `product_commercials`). Domain: `product_catalog`, owned by `retailpulses/RPagentOS`.

## Workflow

### 1. Confirm the working inputs

Prefer the live defaults from [references/workflow.md](references/workflow.md) unless the user gives replacements:

- Supabase project credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`)
- `product_variants` (via `baserow_886994_compat_vw`)
- `amazon_listings` table
- official Amazon `PriceAndQuantity.xlsm` template path
- target output folder

If the user gave a processing summary file, treat it as phase 3 input and keep going.

## Supabase Access

Use PostgREST API directly when you need to read, compare, sync, or verify data.

- Authenticate with `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>`.
- Read rows from `{SUPABASE_URL}/rest/v1/baserow_886994_compat_vw?select=*`.
- Use Range headers for pagination when reading large result sets.
- Use the live schema before assuming field names if table structure may have changed.
- For bulk inventory sync, build a map from `product_variants.item_code` to the computed quantity.
- Quantity Rule: `Max(Qty Available, Owned Qty, Presale Qty)`.
- Restock Policy: If `Presale Qty` is used, then `Restock date` is mandatory to use the presale count; otherwise fallback to `Max(Qty Available, Owned Qty)`.
- Match `amazon_listings.item_code` to `product_variants.item_code`.
- Write `amazon_listings.quantity` and `amazon_listings.last_synced_at` during inventory sync.
- Use PostgREST PATCH with batch operations for inventory updates.
- Keep syncs append-free and non-destructive: do not create or delete rows in this workflow.

### 2. Sync Supabase inventory first

Run:

```bash
python3 scripts/sync_supabase_inventory.py \
  --supabase-url "$SUPABASE_URL" \
  --supabase-key "$SUPABASE_SERVICE_ROLE_KEY" \
  [--dry-run] [--confirm]
```

This reads `product_variants` inventory quantities and writes them to `amazon_listings`.

### 3. Generate the Amazon inventory flatfile

Run:

```bash
python3 scripts/build_inventory_flatfile.py \
  --template <PriceAndQuantity.xlsm> \
  --output <output_dir> \
  [--supabase-url "$SUPABASE_URL"] \
  [--supabase-key "$SUPABASE_SERVICE_ROLE_KEY"]
```

Reads from `amazon_listings` and generates the inventory upload file.

### 4. Generate processing summary report (if applicable)

If the user provides an Amazon processing summary file:

```bash
python3 scripts/summarize_processing_summary.py \
  --summary <processing_summary.txt> \
  --output <output_dir>
```

## Credentials

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — service_role key for reads/writes
- `BASEROW_TOKEN` (legacy) — no longer used; ignore if present

## References

- `references/workflow.md` — Verified defaults, matching rules, and failure modes
- `scripts/sync_supabase_inventory.py` — Supabase inventory sync (replaces legacy sync_baserow_inventory.py)
- `scripts/build_inventory_flatfile.py` — Amazon flatfile builder
- `scripts/summarize_processing_summary.py` — Processing summary report generator
