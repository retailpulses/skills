# Amazon Inventory Workflow Defaults

## Verified workflow

This workflow was validated on 2026-03-28. Updated 2026-07-18 for Supabase migration.

Working sequence:

1. Update Supabase `amazon_listings` inventory from `product_variants` (via `baserow_886994_compat_vw`)
2. Generate a tab-delimited upload file from the official Amazon `PriceAndQuantity.xlsm` template
3. Upload to Amazon
4. Read the processing summary
5. Generate an execution report

## Verified Supabase defaults

- Source: `baserow_886994_compat_vw` (joins `product_variants` + `product_commercials`)
- Target: `amazon_listings` table
- Domain: `product_catalog`, owned by `retailpulses/RPagentOS`

## Supabase API access

- Read rows with `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>`.
- Use PostgREST: `GET /rest/v1/baserow_886994_compat_vw?select=*`.
- Use Range headers for pagination on large result sets.
- For inventory sync, build the lookup from `product_variants.item_code` and write `amazon_listings.quantity`.
- Use batch PATCH via PostgREST for inventory updates.

Field mapping:

- `product_variants.item_code` -> `amazon_listings.item_code`
- Computed quantity (Max of Qty Available, Owned Qty, Presale Qty) -> `amazon_listings.quantity`

Unmatched behavior:

- if an `amazon_listings` row does not match a `product_variants.item_code`, write `0` into `quantity`

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
