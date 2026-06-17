---
name: sync-giga-saved-products
description: Sync GigaB2B products into Baserow Products table 886994 / product master from explicit Item Codes or recently saved GigaB2B products. Use when the user asks to upload, import, backfill, create, update, or normalize GigaB2B products in Baserow Products, product master, or table 886994. The workflow resolves saved-product SKUs, enriches from Giga detailInfo, price, and inventory APIs, writes complete normalized Products rows, skips duplicates by default, and updates existing rows only when explicitly requested.
---

# Sync Giga Products To Baserow Products

Use this skill to land complete, normalized GigaB2B product data into Baserow `Products` table `886994`.

Treat "saved products" as one input mode only. The product-master payload must come from the richer GigaB2B detail, price, and inventory endpoints, not only from the saved-products list.

## Source Of Truth

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

## Baserow Workflow

1. Load the live schema for table `886994` before writing.
2. Resolve the `Item Code` field ID from the live schema.
3. Fetch formula fields from the live schema and remove them from payloads before writing.
4. Use exact server-side filtering by `Item Code`; do not rely on fuzzy `search` for duplicate checks.
5. Skip existing `Item Code` rows by default.
6. Update existing rows only if the user explicitly asks for update/backfill/refresh mode.
7. Verify created or updated rows by re-reading them from Baserow.
8. Do not create a Baserow job log unless the user explicitly asks for one.

## Write Modes

- Default mode: create missing Products rows only.
- Dry-run first when doing live product-master writes unless the user explicitly asks to execute immediately.
- Update mode: patch existing Products rows only when the user explicitly asks for updates/backfills/refreshes.
- This skill writes only to Baserow `Products` table `886994`.

## Products Field Mapping

Build the Baserow `886994` payload from Giga `detailInfo`, `price`, and `inventory` using the canonical implementation. The current normalized Products fields include:

| Baserow field | Source / rule |
|---|---|
| `item code` | `detail.sku` or `price.sku` or `inventory.sku` |
| `Product Name` | `detail.productName` |
| `Store Code` | `price.sellerInfo.sellerCode` |
| `Store Name` | `price.sellerInfo.sellerStore` |
| `Seller Type` | `price.sellerInfo.sellerType` |
| `GIGA Index` | stringified `price.sellerInfo.gigaIndex` |
| `Unit Price` | `price.price` |
| `Discounted Unit Price` | `price.discountedPrice` |
| `Exclusive Price` | `price.exclusivePrice` |
| `MAP` | `price.mapPrice` |
| `Unit Fulfillment Fee (Drop Shipping)` | `price.shippingFee` |
| `Start From` | date-only `price.promotionFrom` |
| `Discount Promotion End Time` | `price.promotionTo` |
| `Effective Cost Price` | rounded first valid value from Exclusive, Discounted, Unit |
| `First Arrival Date` | `detail.firstArrivalDate` |
| `Product Main Image` | `detail.mainImageUrl`, falling back to first `detail.imageUrls[]` value when needed |
| `Image URLs JSON` | JSON array of de-duplicated image URLs from `Product Main Image` plus `detail.imageUrls[]` |
| `Product Images (exclude main)1..26` | de-duplicated `detail.imageUrls[]` values after removing the main image |
| `Main Color` | `detail.mainColor` |
| `Representative_Color_JA` | field `8188238`; Japanese color translated from `detail.mainColor`, or existing Japanese `detail.mainColor`; leave blank when no safe Japanese value can be derived |
| `Main_Material` | `detail.mainMaterial` |
| `Marketing Description` | `detail.description` |
| `User Manual URL` | first value in `detail.fileUrls` |
| `Product Features` | cleaned Giga `characteristics` joined as Japanese bullet lines |
| `Product Specification` | attributes + description + characteristics |
| `Combo Product?` | boolean `detail.comboFlag` |
| `Package Size-Width (cm)` | numeric `detail.widthCm` |
| `Package Size-Length (cm)` | numeric `detail.lengthCm` |
| `Package Size-Height (cm)` | numeric `detail.heightCm` |
| `Package Size-Weight (kg)` | numeric `detail.weightKg` |
| `Assembled Size-Width (cm)` | numeric `detail.assembledWidth` |
| `Assembled Size-Length (cm)` | numeric `detail.assembledLength` |
| `Assembled Size-Height (cm)` | numeric `detail.assembledHeight` |
| `Product Weight (kg)` | numeric `detail.assembledWeight` |
| `Internal_Cat_Name` | `detail.category`, JSON-stringified if non-string |
| `Internal_CAT_ID` | stringified `detail.categoryCode` |
| `Qty Available` | `inventory.sellerInventoryInfo.sellerAvailableInventory` |
| `Owned Qty` | `inventory.buyerInventoryInfo.totalBuyerAvailableInventory` |
| `More On The Way` | stringified `nextArrivalInventory.nextArrivalQtyMax` |
| `nextArrivalBegain` | stringified `nextArrivalInventory.nextArrivalBegin` |
| `nextArrivalEnd` | stringified `nextArrivalInventory.nextArrivalEnd` |
| `Inventory Status` | `in_stock` when Giga says SKU is available, otherwise `unavailable` |
| `Platform_Attributes_JSON` | JSON containing raw `giga_detail`, `giga_price`, and `giga_inventory` |

Do not write Baserow formula fields such as computed discount fields.
Do not write legacy `Estimated Next Arrival Date`; write `nextArrivalBegain` and `nextArrivalEnd` directly instead.

## Data Quality Rules

- Treat `Item Code` as the unique key.
- Skip ghost SKUs when Giga detail has no `productName`, no `description`, and no `mainImageUrl`.
- Do not invent values absent from GigaB2B or Baserow.
- Keep raw Giga payloads in `Platform_Attributes_JSON` for traceability.
- Preserve existing Baserow rows in default create-only mode.
- Propagate parent pricing to variant SKUs only when using the canonical implementation's variant-pricing step.
- Report counts for created, updated, skipped, ghosts, errors, and verification results.

## Credentials

Use environment variables only:

- `BASEROW_TOKEN`
- `BASEROW_BASE_URL`, optional, default `https://api.baserow.io`
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
- Load live Baserow schema and strip formula fields.
- Fetch saved-products SKUs when needed.
- Fetch Giga detail, price, and inventory data for target SKUs.
- Create or update Baserow Products according to the requested mode.
- Verify written rows by exact `Item Code`.
- Summarize created, updated, skipped, ghosts, errors, and verification results.

## References

- `references/GIGAB2B_API_ACCESS.md` for saved-products API access details.
- `/Users/user/Documents/Retailpulses/20_REPOS/listing-mgmt/tools/shared/giga-sync/giga_baserow_sync.py` for the current normalized Products-table implementation.
