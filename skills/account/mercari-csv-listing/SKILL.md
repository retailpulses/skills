---
name: mercari-listing
description: Build a Mercari listing CSV from a list of Item Codes by joining live Baserow product data, pricing/inventory data, shipping lookup data, and Mercari copywriting output. Use when the user asks for a Mercari listing CSV, a Mercari upload file, or to generate the current Mercari CSV template from item codes.
---

# Mercari Listing

Use this skill when the input is a list of `Item Code` values and the output should be a Mercari listing CSV named with the generation date.

## Workflow

1. Deduplicate the input item codes.
2. Inspect the live schema for the required Baserow tables.
3. Preprocess `912520` images over `10MB` to `1500x1500` progressive JPEG, upload to Cloudflare R2, and write back the replacement URL.
4. Resolve product data from `912520`, pricing/inventory from `886994`, and shipping lookup data from `914491`.
5. Confirm a Mercari copy row exists in `912536`; if missing, generate it first with `giga-resource-pack-copywriting`.
6. Assemble one CSV row per `Item Code` using the current Mercari template schema.
7. Verify title length, required defaults, and lookup-driven values.
8. Optional: upload the CSV to Mercari shops by API with per-shop SKU dedupe.

### Required image preprocessing run

Use scripts in `scripts/` before generating the Mercari CSV:

```bash
# optional: create/ensure dedicated R2 bucket (name will be normalized)
bash scripts/create_resize_product_images_bucket.sh "Resize Product Images" "$WRANGLER_CONFIG"

# required: replace only oversize images (>10MB), then write back URLs to Baserow
# token can come from --token or BASEROW_TOKEN env (.env/.env.local supported)
python3 scripts/prepare_oversize_images_for_mercari.py \
  --table-id 912520 \
  --r2-bucket "Resize Product Images" \
  --r2-public-base-url "$R2_PUBLIC_BASE_URL" \
  --wrangler-config "$WRANGLER_CONFIG"
```

### Recommended CSV generation command (Item Code direct lookup)

```bash
python3 scripts/build_mercari_listing_csv.py \
  --item-codes "$ITEM_CODES_OR_FILE" \
  --template-csv "$MERCARI_TEMPLATE_CSV" \
  --shipping-guide-url "$SHIPPING_FEE_GUIDE_URL" \
  --output-path "$OUTPUT_CSV_PATH"
```

- This script uses Baserow server-side exact filtering by `Item Code` for `912520`, `886994`, and `912536`, avoiding full-table pagination when item codes are provided.
- It now resolves Baserow field IDs first and filters by `filter__field_<id>__equal`, which is more robust when field names include spaces/case variants.
- If Mercari copy is missing for an item, the script auto-runs designated skill `giga-resource-pack-copywriting` runner (`scripts/generate_copywriting_rows.py`) to create missing Mercari copy, then continues CSV build.
- If designated skill execution still cannot produce copy for some Item Codes, CSV build fails by default with the remaining missing list.
- Default CSV output encoding is `utf-8-sig` (BOM) to avoid mojibake when opening directly on macOS.

### Optional API upload to 4 shops (skip existing)

```bash
# dry run
python3 scripts/upload_mercari_csv_to_shops.py \
  --csv "$OUTPUT_CSV_PATH" \
  --shops "shop1,shop2,shop3,shop4" \
  --mode ssh \
  --dry-run

# production
python3 scripts/upload_mercari_csv_to_shops.py \
  --csv "$OUTPUT_CSV_PATH" \
  --shops "shop1,shop2,shop3,shop4" \
  --mode ssh
```

- For each row and shop, the uploader first checks `productVariant(by: { skuCode })`.
- If SKU already exists in that shop, the row is skipped for that shop.
- If create returns an error, the uploader still re-checks by SKU and reconciles final status.
- Variant name should come from `SKU1_種類` when present; do not hardcode `Default`. If `SKU1_種類` is blank, omit the variant name.

### Secret handling

- Do not hardcode secrets in `SKILL.md`.
- Put `BASEROW_TOKEN` in environment variables or in skill-local `.env` / `.env.local`.
- Use `.env.example` as the template.

## Baserow Access

- Authenticate with `Authorization: Token <database token>`.
- Read rows with `user_field_names=true` so the live field labels are usable as keys.
- Page through tables with `size=200&page=<n>` when reading more than one page.
- Confirm the live schema before assuming field names or table roles.
- Source tables are `912520`, `886994`, and `912536`.
- Use exact `Item Code` matching as the join key across those tables.
- Do not invent values when a lookup is missing; leave the target field blank and report it.
- Keep Baserow reads and CSV generation separate; this skill builds the local CSV output only.

## Source Rules

- Use exact `Item Code` matching as the linkage key across tables.
- Use live Baserow data only; do not rely on stale local snapshots.
- Do not invent values for pricing, category, stock, or shipping fields.
- If a lookup is missing, leave the target field blank and report it.
- Preserve the current CSV column order from the reference template.

## Title Rules

- Base the title on the Mercari copywriting row for the item.
- If the effective discount is over `10%`, prepend `数量限定セール`.
- Derive the effective discount from `Discounted Unit Price` or `Exclusive Price` versus `Unit Price`.
- If a future restock date exists, prepend `MM/DD再入荷予定`.
- If both prefixes apply, keep both prefixes and keep them at the start of the title.
- Keep the final title within `130` characters.
- When trimming is needed, remove secondary descriptors first and keep the core product name intact.

## Field Rules

- `商品名` = Mercari title
- `商品説明` = Mercari description
- `SKU1_商品管理コード` = `Item Code`
- `SKU1_種類` = `Main Color (JP)` from `886994`; if blank, leave `SKU1_種類` blank / `NULL`
- `販売価格` = `Mercari ref pricing`
- `SKU1_現在の在庫数` = `Mercari Qty`
- `カテゴリID` = `Mercari category ID`
- `送料ID` = shipping bracket from `914491`; if the fee falls between brackets, round up to the next available bracket instead of leaving the field blank
- `商品の状態` = `1`
- `配送方法` = `1`
- `発送元の地域` = `jp13`
- `発送までの日数` = `5` when `Mercari Qty = 5`, otherwise `1`
- `商品ステータス` = `1` to keep listings unopened for manual review; the upload layer maps this to `UNOPENED`
- `配送料の負担` = `2`; the upload layer must map this workflow to buyer-paid shipping (`BUYER`) when a shipping config ID is present
- Leave `SKU2` through `SKU10` blank and leave other unspecified fields blank.

Critical case:

- Do not remove the `送料ID` lookup just because `createProduct` debugging points at `shippingConfigurationId`. `送料ID` is a required CSV shipping-field value and must stay populated from the shipping bracket logic unless the user explicitly asks to change the Mercari shipping model.
- Critical case: if Mercari rejects `shippingConfigurationId` on an existing listing, verify the payer enum first. The live API accepts `shippingConfigurationId` only when `shippingPayer=BUYER`; `SELLER` will return `request parameter is invalid`.

## Image Rules

- Process only source images over `10MB`.
- Resize to `1500x1500` max bounds with progressive JPEG output.
- Upload resized files to the `Resize Product Images` R2 bucket and write back the replacement URL to `912520`.
- Fill image columns from `Product Main Image`, then `Product Images (exclude main)1..26`, then `Additional Images`.
- Fill up to `商品画像名_20`; if there are fewer than 20 source images, append the shipping-fee guide image in the last used slot; if there are 20 or more source images, replace slot 20 with the shipping-fee guide image URL.
- Preserve the template image flag pattern unless the user explicitly asks to rewrite it.

## Output Rules

- Write the final file as `mercari_listing_YYYY-MM-DD.csv` by default.
- Preserve all template columns, even if many remain blank.
- Verify the final CSV before delivery.

## References

- See [mercari-csv-listing-schema.md](references/mercari-csv-listing-schema.md) for the table mappings and CSV column conventions.
- See [image-preprocessing-r2.md](references/image-preprocessing-r2.md) for the R2 image processing flow and command usage.
- See [api-upload-multishop.md](references/api-upload-multishop.md) for CSV-to-API upload to 4 shops with skip-existing behavior.
