---
name: gigab2b-workflow
description: Combined skill for GigaB2B API query access (product detail, price, shipping, saved-products), sync workflow, and patch-incomplete mode for Baserow table 886994, using HMAC-SHA256 signed requests.
---

# GigaB2B Workflow

Use this skill when you need to either query GigaB2B product, price, shipping, or saved-product data, or sync saved products into Baserow table 886994.

This skill is self-contained for GigaB2B operations. Do not rely on external repo docs during normal use.

## Prerequisites

- `GIGA_CLIENT_ID` environment variable
- `GIGA_CLIENT_SECRET` environment variable
- `GIGA_API_BASE_URL` environment variable (defaults to `https://openapi.gigab2b.com`)
- Baserow token (set as `BASEROW_TOKEN` or `RP_BASEROW_TOKEN`)

## Authentication

All API requests to GigaB2B use HMAC-SHA256 signed headers.

Required inputs:

- `GIGA_CLIENT_ID`
- `GIGA_CLIENT_SECRET`
- `GIGA_API_BASE_URL` defaulting to `https://openapi.gigab2b.com`

### Credential Hygiene

- Prefer reading credentials from local workspace config or environment only.
- Common local sources include `.env`, `wrangler.toml`, `wrangler-test.toml`, and deployment secret stores.
- Never print `clientId`, `clientSecret`, signed headers, or raw auth payloads in outputs.
- If credentials are discovered in workspace files, load them into memory only for the request and treat them as sensitive.
- If a required credential is missing, stop rather than fabricating a placeholder.
- When reporting results, summarize only success, status codes, request IDs, and errors.

### Signature Formula

- `message = clientId & apiPath & timestamp & nonce`
- `key = clientId & clientSecret & nonce`
- `sign = base64(HMAC-SHA256(message, key).hex())`

### Required Headers for POST Requests

- `Content-Type: application/json`
- `client-id`
- `timestamp`
- `nonce`
- `sign`

### Nonce

- Use a 10-digit random numeric string.

### Timestamp

- Use milliseconds since Unix epoch.
- Keep the request within the API's allowed freshness window.

## Query Mode

Use these endpoints for direct data queries.

### Endpoint Selection

1. **Saved products / collection list**
   - Use `POST /b2b-overseas-api/v1/buyer/product/skus/v1`
   - Use for saved-products syncs, full-history audits, or recent-add scans.
   - Prefer `queryTimeType = 2` when filtering by saved time window.

2. **Product detail**
   - Use `POST /b2b-overseas-api/v1/buyer/product/detailInfo/v1`
   - Use for metadata such as description, images, dimensions, attributes, availability, or seller info.
   - Exactly one of `skus` or `productNames` must be provided.
   - Limit: 200 items per request.

3. **Price**
   - Use `POST /b2b-overseas-api/v1/buyer/product/price/v1`
   - Use when the user needs `price`, `exclusivePrice`, `discountedPrice`, or `skuAvailable`.
   - Send `skus` only.
   - Limit: 200 items per request.

4. **Shipping / tracking**
   - Use `POST /b2b-overseas-api/v1/buyer/order/track-no/v1`
   - Use for package tracking numbers, carriers, or return-label tracking.
   - Send `orderNo`.
   - Limit: 100 order numbers per request.

### Operating Workflow

1. Identify the data type the user actually needs.
2. Select the matching endpoint from the matrix above.
3. Build the JSON body with only required fields.
4. Sign the request with the current timestamp and a 10-digit nonce.
5. Call the API and inspect both HTTP status and JSON `success`.
6. If the response is partial or empty, verify the requested key type, batch size, and endpoint choice before retrying.

### Validation Notes

- Product detail supports SKU or product-name lookup, but not both at once.
- Price requests should be interpreted using the API's own `price`, `exclusivePrice`, and `discountedPrice` fields.
- Shipping responses can include multiple package-level tracking entries per order.
- Saved-products responses are paginated and should be read until all pages are exhausted.

## Sync Mode

Use this mode to fetch saved products from GigaB2B and write them to Baserow table 886994.

### Input Modes

1. Explicit `Item Code` list.
2. Default mode: newly added saved products from the last 30 days.

If the user does not clearly specify a mode, ask which mode to use.

### Workflow

1. Read the user input and normalize the requested mode.
2. Load the live Baserow schema for table `886994` before writing anything.
3. Use the GigaB2B saved-products API endpoint (`POST /b2b-overseas-api/v1/buyer/product/skus/v1`) to fetch the requested saved-product set.
4. Deduplicate the source set by `Item Code`.
5. Query Baserow `886994` and build the existing `Item Code` set.
6. Skip any source row whose `Item Code` already exists.
7. Create new Baserow rows only for new `Item Code` values.
8. Leave unrelated fields unchanged or blank unless the source data provides a safe value.
9. Verify the write result by re-reading the created rows.

### Write Rules

- `Item Code` is the unique key.
- Never create a duplicate row for an existing `Item Code`.
- Never update existing rows unless the user explicitly asks for an update workflow.
- Do not invent source values that are not present in GigaB2B or Baserow.
- Keep the operation append-only.

### Default Behavior

- If the user gives explicit item codes, sync only those codes.
- If the user gives no item codes and no other mode hint, use the last-30-days saved-products sync.
- If the saved-products retrieval path is unclear from the repo context, stop and confirm before guessing.

### Baserow Access

- Read Baserow rows with the live API and `user_field_names=true`.
- Target table for this skill: `886994`.
- Treat `Item Code` as the unique lookup key.
- For reads, fetch existing rows first and build a set of existing `Item Code` values.
- For writes, POST only the new rows that do not already exist.
- Keep the workflow append-only unless the user explicitly asks for updates.
- Do not invent values for fields that are not present in the source row.

### Saved-Products Response Fields

Response fields used by this skill:
- `data.records[].sku`
- `data.records[].productName`
- `data.records[].updateTime`
- `data.records[].firstArrivalDate`
- `data.records[].addedTime`

Request body for the last-30-days sync:
- `queryTimeType = 2`
- `startTime`
- `endTime`
- `page`
- `pageSize = 100`
- `sort = 4`

The last-30-days mode should be interpreted as collection/saved time, not product creation time.

## Patch Incomplete Mode

Use this mode to find products in Baserow table 886994 that have blank mandatory fields and fill them in using GigaB2B detail and price API data.

### When to Use

- After a sync that created rows with only `Item Code` + `Product Name`.
- When products have hollow records — blank `Product Features`, `Product Specification`, `Store Code`, etc.
- When the user asks to "fill in missing product data" or "patch incomplete products".

### Input Modes

1. **Scan all rows** — fetch all rows from 886994, identify incomplete ones, and patch them.
2. **Explicit Item Code list** — patch only the specified Item Codes.
3. **Limit mode** — patch up to N incomplete products (e.g., `--limit 50`).

If the user does not specify a mode, default to scanning all rows with a dry-run first to report counts.

### Mandatory Fields (Completeness Check)

A product row is **incomplete** if ANY of these fields is blank/null/empty:

| Field | Priority | Source API |
|---|---|---|
| `Product Name` | Critical | Detail API |
| `Product Features` | Critical | Detail API (built from `characteristics[]`) |
| `Product Specification` | Critical | Detail API (built from `description` + `attributes` + dimensions) |
| `Store Code` | High | Detail API (`sellerCode`) |
| `Store Name` | High | Detail API (`sellerStore`) |
| `Product Main Image` | High | Detail API (`mainImageUrl` or `imageList[0]`) |
| `Image URLs JSON` | High | Detail API (`imageList[]` serialized as JSON array) |
| `Unit Price` | High | Price API (`unitPrice`) |
| `Unit Fulfillment Fee (Drop Shipping)` | High | Detail API (`fulfillmentFee`) or Price API |

A row is considered "incomplete" even if only one of these fields is blank. The patch operation should fill ALL blank mandatory fields in a single PATCH per row.

### Workflow

#### Phase 1: Discover Incomplete Rows

1. **Fetch all rows from Baserow 886994** with `user_field_names=true`, paginated (size=200).
2. For each row, check the mandatory fields listed above.
3. Build a list of incomplete rows: `{row_id, item_code, missing_fields: [...]}`.
4. If `--dry-run` is set, **report counts and stop** — do not call GigaB2B or write anything.

Report format for dry-run:
```
Total rows scanned: 1,234
Incomplete rows found: 342
  Missing Product Name: 5
  Missing Product Features: 310
  Missing Product Specification: 298
  Missing Store Code: 45
  Missing Store Name: 45
  Missing Product Main Image: 120
  Missing Image URLs JSON: 130
  Missing Unit Price: 15
  Missing Unit Fulfillment Fee (Drop Shipping): 200
```

#### Phase 2: Fetch Rich Data from GigaB2B

For each incomplete row, we need data from two APIs:

**Detail API** (`POST /b2b-overseas-api/v1/buyer/product/detailInfo/v1`):
- Send `skus` in batches of up to 200.
- Response fields used: `productName`, `description`, `characteristics[]`, `attributes[]`, `sellerCode`, `sellerStore`, `mainImageUrl`, `imageList[]`, `packageWeight`, `packageLength`, `packageWidth`, `packageHeight`, `fulfillmentFee`.

**Price API** (`POST /b2b-overseas-api/v1/buyer/product/price/v1`):
- Send `skus` in batches of up to 200.
- Response fields used: `unitPrice`.

Call both APIs for the full set of incomplete SKUs. Merge results keyed by SKU.

#### Phase 3: Build Patches

For each incomplete row, construct a PATCH payload containing ONLY the fields that are currently blank AND have data available from the APIs:

**`Product Name`** — use `productName` from detail API.

**`Product Features`** — Build a formatted string from `characteristics[]`:
```
Brand: {brand}
Material: {material}
Color: {color}
Style: {style}
...
```
If `characteristics[]` is empty, construct from `attributes[]` key-value pairs.
Format as one feature per line, with the key in bold or as a label: `**Key:** Value`.

**`Product Specification`** — Build a formatted string combining:
- `description` (product description text)
- Dimensions: `Assembled Size: {length}×{width}×{height} cm`
- Weight: `Product Weight: {weight} kg`
- Package: `Package Size: {pkgLength}×{pkgWidth}×{pkgHeight} cm, {pkgWeight} kg`
- Country of origin (from `attributes[]`)
- Any other relevant attributes

Format as sections with clear headers. Use Japanese labels if the product is for Japan marketplaces.

**`Store Code`** — use `sellerCode` from detail API.

**`Store Name`** — use `sellerStore` from detail API.

**`Product Main Image`** — use `mainImageUrl` if present; otherwise use the first URL from `imageList[]`.

**`Image URLs JSON`** — serialize ALL URLs from `imageList[]` as a JSON array string:
```json
["https://img.gigab2b.com/...", "https://img.gigab2b.com/..."]
```
Only include the JSON array, not an object wrapper.

**`Unit Price`** — use `unitPrice` from price API (number, not string).

**`Unit Fulfillment Fee (Drop Shipping)`** — use `fulfillmentFee` from detail API or shipping-related field from price API. If both APIs have a value and they differ, prefer the detail API value and note the discrepancy.

#### Phase 4: Apply Patches

1. Sort patches by priority: rows with more missing critical fields first.
2. PATCH each row individually via `PATCH /api/database/rows/table/886994/{row_id}/?user_field_names=true`.
3. Use the Baserow database token (`BASEROW_TOKEN` or `RP_BASEROW_TOKEN`).
4. Rate-limit: wait at least 100ms between PATCH calls to avoid API throttling.
5. Track successes and failures.

#### Phase 5: Verify & Report

1. After all patches are applied, re-read a sample of patched rows (at least 10% or 10 rows, whichever is larger).
2. Verify that previously-blank fields are now populated.
3. Verify that previously-populated fields were NOT overwritten.
4. Report:

```
Patch Incomplete Products — Complete

Rows scanned: 1,234
Incomplete found: 342
Successfully patched: 338
Failed: 4
  - SKU ABC123: Baserow API error 500
  - SKU DEF456: Detail API returned empty data
  - SKU GHI789: Price API timeout
  - SKU JKL012: No detail data found for this SKU

Fields filled:
  Product Name: 3
  Product Features: 305
  Product Specification: 290
  Store Code: 40
  Store Name: 40
  Product Main Image: 115
  Image URLs JSON: 125
  Unit Price: 12
  Unit Fulfillment Fee (Drop Shipping): 195

Verification: 10 rows spot-checked — all patches correct, no overwrites detected.
```

### Safety Rules

- **Never overwrite existing data.** For each field, check if it's blank BEFORE building the patch. If a field has a value, skip it — do not include it in the PATCH payload.
- **Never invent data.** If the GigaB2B APIs don't return a value for a field, leave it blank. Do not fabricate, infer, or guess.
- **Dry-run first.** Always offer `--dry-run` as the first step so the user can see counts before any writes happen.
- **Limit mode.** Support `--limit N` to cap the number of products patched in a single run.
- **Batch size.** Send at most 200 SKUs per detail/price API call (the GigaB2B API limit).
- **Idempotent.** Running the patch mode twice should be safe — the second run finds nothing to patch (all fields already filled).
- **Handle missing SKUs.** If the detail API returns no data for a SKU (e.g., product was delisted), skip that row and report it as "not found in GigaB2B."
- **Stop on auth failure.** If GigaB2B or Baserow auth fails, stop immediately and report which credential is missing/broken.

### Credentials Used

- Same as Query/Sync modes: `GIGA_CLIENT_ID`, `GIGA_CLIENT_SECRET`, `GIGA_API_BASE_URL`
- Baserow: `BASEROW_TOKEN` or `RP_BASEROW_TOKEN`

## Shared Resources

- Request signing script: `../gigab2b-api-access/scripts/giga_request.py`
- Baserow table registry: `../references/baserow_tables.md`
