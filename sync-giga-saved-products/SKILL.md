---
name: sync-giga-saved-products
description: Sync GigaB2B products into Supabase product_variants + product_commercials from explicit Item Codes or recently saved GigaB2B products. Use when the user asks to upload, import, backfill, create, update, or normalize GigaB2B products. The workflow resolves saved-product SKUs, enriches from Giga detailInfo, price, and inventory APIs, writes complete normalized rows, skips duplicates by default, and updates existing rows only when explicitly requested.
---

# Sync Giga Products To Supabase

Use this skill to land complete, normalized GigaB2B product data into Supabase `product_variants` and `product_commercials`.

## Backend

Supabase is the only backend. The legacy Baserow 886994 path has been retired.

| Backend | Script | Target |
|---------|--------|--------|
| Supabase | `scripts/sync_to_supabase.py` | `product_variants` + `product_commercials` |

Treat "saved products" as one input mode only. The product-master payload must come from the richer GigaB2B detail, price, and inventory endpoints, not only from the saved-products list.

## Source Of Truth

The canonical Supabase schema is owned by `retailpulses/RPagentOS` (domain: `product_catalog`). Do not create or alter schema objects from this skill.

Prefer the implementation and field mapping in:

- `/Users/user/Documents/Retailpulses/20_REPOS/listing-mgmt/tools/shared/giga-sync/giga_baserow_sync.py`

If that repo path is unavailable, use the same file under:

- `/Users/user/Documents/Retailpulses/20_REPOS/workers/shared/giga-sync/giga_baserow_sync.py`

Read the implementation before running or reimplementing the workflow. It contains the current Products payload builder, formula-field stripping, exact `Item Code` lookup, create/update behavior, ghost-SKU handling, and variant pricing propagation.

## Input Modes

Support these modes:

1. Explicit `Item Code` / SKU list.
2. Recently saved GigaB2B products, defaulting to the last 30 days when no item codes are provided.

If the user does not clearly specify item codes or a saved-products time window, use the last-30-days saved-products mode.

## Required API Flow

For saved-products mode:

1. Fetch saved products from `POST /b2b-overseas-api/v1/buyer/product/skus/v1`.
2. Interpret the time window as saved/collection time, using `queryTimeType = 2`.
3. Deduplicate by SKU / `Item Code`, keeping the newest `addedTime`.
4. Use the resulting SKU list as input to the product-master sync.

For product-master enrichment, batch SKUs and call:

- `POST /b2b-overseas-api/v1/buyer/product/detailInfo/v1`
- `POST /b2b-overseas-api/v1/buyer/product/price/v1`
- `POST /b2b-overseas-api/v1/buyer/inventory/quantity/v2`

Do not create a Products row from the saved-products response alone. It is not complete enough.

## Workflow

1. Read the live Supabase schema for `product_variants` and `product_commercials` before writing.
2. Resolve column names from the live schema.
3. Use exact server-side filtering by `item_code`; do not rely on fuzzy search for duplicate checks.
4. Skip existing `item_code` rows by default.
5. Update existing rows only if the user explicitly asks for update/backfill/refresh mode.
6. Verify created or updated rows by re-reading them via PostgREST.
7. Do not create a job log unless the user explicitly asks for one.

## Write Modes

- Default mode: create missing rows only.
- Dry-run first when doing live product-master writes unless the user explicitly asks to execute immediately.
- Update mode: patch existing rows only when the user explicitly asks for updates/backfills/refreshes.
- This skill writes only to `product_variants` and `product_commercials`.

## Products Field Mapping

Build the Supabase payload from Giga `detailInfo`, `price`, and `inventory` using the canonical implementation. The current normalized fields include:

| Supabase column | Source / rule |
|---|---|
| `item_code` | `detail.sku` or `price.sku` or `inventory.sku` |
| `product_name` | `detail.productName` |
| `store_code` | `price.sellerInfo.sellerCode` |
| `store_name` | `price.sellerInfo.sellerStore` |
| `seller_type` | `price.sellerInfo.sellerType` |
| `giga_index` | stringified `price.sellerInfo.gigaIndex` |
| `unit_price` | `price.price` |
| `discounted_unit_price` | `price.discountedPrice` |
| `exclusive_price` | `price.exclusivePrice` |
| `map_price` | `price.mapPrice` |
| `shipping_fee` | `price.shippingFee` |
| `promotion_from` | date-only `price.promotionFrom` |
| `promotion_to` | `price.promotionTo` |
| `effective_cost_price` | rounded first valid value from Exclusive, Discounted, Unit |
| `first_arrival_date` | `detail.firstArrivalDate` |
| `main_image_url` | `detail.mainImageUrl`, falling back to first `detail.imageUrls[]` value when needed |
| `image_urls_json` | JSON array of de-duplicated image URLs from main image plus `detail.imageUrls[]` |
| `main_color` | `detail.mainColor` |
| `representative_color_ja` | Japanese color translated from `detail.mainColor`, or existing Japanese `detail.mainColor`; leave blank when no safe Japanese value can be derived |
| `main_material` | `detail.mainMaterial` |
| `marketing_description` | `detail.description` |
| `user_manual_url` | first value in `detail.fileUrls` |
| `product_features` | cleaned Giga `characteristics` joined as Japanese bullet lines |
| `product_specification` | attributes + description + characteristics |
| `combo_product` | boolean `detail.comboFlag` |
| `package_width_cm` | numeric `detail.widthCm` |
| `package_length_cm` | numeric `detail.lengthCm` |
| `package_height_cm` | numeric `detail.heightCm` |
| `package_weight_kg` | numeric `detail.weightKg` |
| `assembled_width_cm` | numeric `detail.assembledWidth` |
| `assembled_length_cm` | numeric `detail.assembledLength` |
| `assembled_height_cm` | numeric `detail.assembledHeight` |
| `assembled_weight_kg` | numeric `detail.assembledWeight` |
| `internal_cat_name` | `detail.category`, JSON-stringified if non-string |
| `internal_cat_id` | stringified `detail.categoryCode` |
| `qty_available` | `inventory.sellerInventoryInfo.sellerAvailableInventory` |
| `owned_qty` | `inventory.buyerInventoryInfo.totalBuyerAvailableInventory` |
| `more_on_the_way` | stringified `nextArrivalInventory.nextArrivalQtyMax` |
| `next_arrival_begin` | stringified `nextArrivalInventory.nextArrivalBegin` |
| `next_arrival_end` | stringified `nextArrivalInventory.nextArrivalEnd` |
| `inventory_status` | `in_stock` when Giga says SKU is available, otherwise `unavailable` |
| `platform_attributes_json` | JSON containing raw `giga_detail`, `giga_price`, and `giga_inventory` |

Do not write computed/formula columns.
Do not write legacy `Estimated Next Arrival Date`; write `next_arrival_begin` and `next_arrival_end` directly instead.

## Data Quality Rules

- Treat `item_code` as the unique key.
- Skip ghost SKUs when Giga detail has no `productName`, no `description`, and no `mainImageUrl`.
- Do not invent values absent from GigaB2B or Supabase.
- Keep raw Giga payloads in `platform_attributes_json` for traceability.
- Preserve existing rows in default create-only mode.
- Propagate parent pricing to variant SKUs only when using the canonical implementation's variant-pricing step.
- Report counts for created, updated, skipped, ghosts, errors, and verification results.

## Credentials

Use environment variables only:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GIGA_CLIENT_ID`
- `GIGA_CLIENT_SECRET`
- `GIGA_API_BASE_URL`, optional, default `https://openapi.gigab2b.com`

Do not read or recommend `master_credentials.md` as the default credential source.

## GigaB2B Signing

Use the signed OpenAPI pattern:

- `message = clientId & apiPath & timestamp & nonce`
- `key = clientId & clientSecret & nonce`
- `sign = base64(HMAC-SHA256(message, key).hex())`

Required headers:

- `client-id`
- `timestamp`
- `nonce`
- `sign`
- `Content-Type: application/json`

## Completion Checklist

- Confirm input mode and SKU count.
- Confirm dry-run versus write mode.
- Read live Supabase schema.
- Fetch saved-products SKUs when needed.
- Fetch Giga detail, price, and inventory data for target SKUs.
- Create or update rows according to the requested mode.
- Verify written rows by exact `item_code`.
- Summarize created, updated, skipped, ghosts, errors, and verification results.

## References

- `references/GIGAB2B_API_ACCESS.md` for saved-products API access details.
- `/Users/user/Documents/Retailpulses/20_REPOS/listing-mgmt/tools/shared/giga-sync/giga_baserow_sync.py` for the current normalized implementation.
