# Amazon Inventory Workflow Defaults

## Verified workflow

This workflow was validated on 2026-03-28.

Working sequence:

1. Update Baserow `Amazon listings` inventory from `Products`
2. Generate a tab-delimited upload file from the official Amazon `PriceAndQuantity.xlsm` template
3. Upload to Amazon
4. Read the processing summary
5. Generate an execution report

## Verified Baserow defaults

- `Products` table id: `886994`
- `Amazon listings` table id: `907027`

## Baserow API access

- Read rows with `Authorization: Token <Baserow database token>`.
- Use `user_field_names=true` on reads and batch writes.
- Page through tables with `size=200&page=<n>`.
- For inventory sync, build the lookup from `Products.item code` and write `Amazon listings.在庫数 (JP)` and `Amazon listings.再入荷日 (JP)`.
- Quantity Rule: `Max(Qty Available, Owned Qty, Presale Qty)`.
- Restock Policy: `Presale Qty` is only used if `Restock date` is present and it is greater than `Max(Qty Available, Owned Qty)`.
- Use batch `PATCH` to `/api/database/rows/table/<table_id>/batch/?user_field_names=true` for inventory updates.

Field mapping:

- `Products.item code` -> `Amazon listings.Item Code`
- `Products.Qty Available` / `Products.Owned Qty` / `Products.Presale Qty` -> `Amazon listings.在庫数 (JP)`
- `Products.Restock date` -> `Amazon listings.再入荷日 (JP)`

Unmatched behavior:

- if an `Amazon listings` row does not match a `Products.item code`, write `0` into `在庫数 (JP)` and clear `再入荷日 (JP)`

## Verified Amazon flat file rule

The ad hoc 3-column tab-delimited file was rejected.

Observed failure mode:

- required `sku` field missing
- header names treated as invalid
- `0` records processed

The accepted format was:

- official `PriceAndQuantity.xlsm` template
- template metadata/header rows preserved
- full template column layout preserved
- data rows filled only for:
  - `SKU`
  - `フルフィルメントチャネルコード (JP)`
  - `在庫数 (JP)`
  - `再入荷日 (JP)`
- saved as tab-delimited text

## Processing summary interpretation

Meaningful statuses:

- `成功`: clean success
- `成功 (その他のエラー)`: inventory row processed, but listing has additional non-blocking issues
- failed rows should be treated as actual inventory upload failures

Common non-blocking errors already seen:

- `18155`: price below minimum threshold
- `20017`: remote image host blocked
- `20015`: unsupported image type
- `8541`: catalog conflict such as `manufacturer`

## Default output naming

Use same-folder outputs with current date:

- flat file:
  - `PriceAndQuantity_inventory_full_template_YYYY-MM-DD.txt`
- execution report:
  - `EXECUTION_REPORT_Amazon_inventory_upload_YYYY-MM-DD.md`
