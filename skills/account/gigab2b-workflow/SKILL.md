---
name: gigab2b-workflow
description: Combined skill for GigaB2B API query access (product detail, price, shipping, saved-products) and sync workflow to Baserow table 886994, using HMAC-SHA256 signed requests.
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

## Shared Resources

- Request signing script: `../gigab2b-api-access/scripts/giga_request.py`
- Baserow table registry: `../references/baserow_tables.md`
