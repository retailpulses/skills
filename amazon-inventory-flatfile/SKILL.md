---
name: amazon-inventory-flatfile
description: Update Amazon listing inventory in Baserow, generate Amazon Price and Quantity flat files from the official template, and summarize Amazon processing summaries into execution reports. Use when the user asks to sync `Amazon listings` inventory from `Products`, create an Amazon inventory upload file, inspect a `PriceAndQuantity.xlsm` template, or review an Amazon processing summary after upload.
---

# Amazon Inventory Flatfile

## Overview

Execute the Amazon inventory workflow in three steps:

1. Sync `Amazon listings` inventory from `Products` in Baserow.
2. Generate a valid Amazon inventory upload file from the official `PriceAndQuantity.xlsm` template.
3. If the user provides a processing summary, generate an execution report in Markdown.

Use the scripts in `scripts/` for repeatable work. Read [references/workflow.md](references/workflow.md) when you need the verified defaults, matching rules, and failure modes.

## Workflow

### 1. Confirm the working inputs

Prefer the live defaults from [references/workflow.md](references/workflow.md) unless the user gives replacements:

- Baserow database token
- `Products` table
- `Amazon listings` table
- official Amazon `PriceAndQuantity.xlsm` template path
- target output folder

If the user gave a processing summary file, treat it as phase 3 input and keep going.

## Baserow Access

Use the live Baserow APIs directly when you need to read, compare, sync, or verify data.

- Authenticate with `Authorization: Token <Baserow database token>`.
- Read rows from `https://api.baserow.io/api/database/rows/table/<table_id>/?user_field_names=true`.
- Use pagination with `size=200&page=<n>` when reading full tables.
- Use the live schema before assuming field names if table structure may have changed.
- For bulk inventory sync, build a map from `Products.item code` to the computed quantity.
- Quantity Rule: `Max(Qty Available, Owned Qty, Presale Qty)`.
- Restock Policy: If `Presale Qty` is used, then `Restock date` is mandatory to use the presale count; otherwise fallback to `Max(Qty Available, Owned Qty)`.
- Match `Amazon listings.Item Code` to `Products.item code`.
- Write `Amazon listings.在庫数 (JP)` and `Amazon listings.再入荷日 (JP)` fields during inventory sync.
- Use batch `PATCH` to `/api/database/rows/table/<table_id>/batch/?user_field_names=true` for inventory updates.
- Keep syncs append-free and non-destructive: do not create or delete rows in this workflow.

### 2. Sync Baserow inventory first

Run:

```bash
python3 scripts/sync_baserow_inventory.py \
  --token "$TOKEN" \
  --products-table-id 886994 \
  --amazon-table-id 907027
```

Default behavior:

- match `Amazon listings.Item Code` to `Products.item code`
- write computed quantity into `Amazon listings.在庫数 (JP)`
- write `Products.Restock date` into `Amazon listings.再入荷日 (JP)` if Presale rule is triggered
- if a listing row is unmatched, write `0` and clear restock date
- leave other listing fields untouched

Use `--dry-run` first if the user asks for verification before write.

### 3. Generate the flat file from the official template

Do not generate a minimal custom CSV. Amazon accepted the template-structured tab-delimited file and rejected the ad hoc 3-column file.

Run:

```bash
python3 scripts/build_inventory_flatfile.py \
  --token "$TOKEN" \
  --amazon-table-id 907027 \
  --template-path "/path/to/PriceAndQuantity.xlsm" \
  --output-path "/path/to/PriceAndQuantity_inventory_full_template_YYYY-MM-DD.txt"
```

Required output rules:

- preserve template rows 1-6
- preserve full template column layout
- fill only:
  - `SKU`
  - `フルフィルメントチャネルコード (JP)`
  - `在庫数 (JP)`
  - `再入荷日 (JP)`
- leave all other columns blank
- write a tab-delimited `.txt`
- include the current date in the filename

### 4. Review processing summaries when provided

If the user gives a processing summary, generate a report instead of only paraphrasing the file.

Run:

```bash
python3 scripts/summarize_processing_summary.py \
  --summary-path "/path/to/processing-summary.xlsm" \
  --output-path "/same/folder/EXECUTION_REPORT_Amazon_inventory_upload_YYYY-MM-DD.md"
```

Supported inputs:

- Amazon processing summary `.xlsm`
- text processing summary `.txt`

The report should cover:

- inventory update result
- counts for processed, successful, failed, and success-with-other-errors
- grouped error codes
- affected SKUs
- concise recommendations

### 5. Respond with the right level of detail

If there is no processing summary yet, report:

- Baserow sync result
- file path created
- output format used

If there is a processing summary, report:

- upload result
- whether inventory processing succeeded
- any non-blocking listing errors
- path to the saved Markdown report

## Guardrails

- Verify the official template path before generating the flat file.
- Prefer live schema verification if table names or field names appear to have changed.
- Prefer the live Baserow API and the bundled scripts over ad hoc field assumptions.
- Treat `success with other errors` as inventory processed unless the summary explicitly shows failed rows.
- Do not switch back to a custom minimal CSV format unless the user explicitly asks to experiment again.
