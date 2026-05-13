---
name: gigab2b-api-access
description: Standalone signed OpenAPI 2.0 skill for GigaB2B product, price, saved-products, and shipping queries using client-id/client-secret signing with direct API access.
---

# GigaB2B API Access

Use this skill when you need to call GigaB2B directly, choose the right endpoint for a business request, or verify product, price, saved-product, or shipping data.

This skill is self-contained. Do not rely on external repo docs during normal use.

## Core Rules

- Use the signed OpenAPI 2.0 flow against `https://openapi.gigab2b.com` unless the user explicitly asks for another environment.
- Do not mix this skill with the repo's unrelated OAuth-based Giga flows.
- Always pick the smallest endpoint that answers the request.
- Batch requests when the API supports it, but stay within documented limits.
- Never expose `clientSecret` or signed headers in the final answer.

## Authentication

Required inputs:

- `GIGA_CLIENT_ID`
- `GIGA_CLIENT_SECRET`
- `GIGA_API_BASE_URL` defaulting to `https://openapi.gigab2b.com`

## Credential Hygiene

- Prefer reading credentials from local workspace config or environment only.
- Common local sources include `.env`, `wrangler.toml`, `wrangler-test.toml`, and deployment secret stores.
- Never print `clientId`, `clientSecret`, signed headers, or raw auth payloads in outputs.
- If credentials are discovered in workspace files, load them into memory only for the request and treat them as sensitive.
- If a required credential is missing, stop rather than fabricating a placeholder.
- When reporting results, summarize only success, status codes, request IDs, and errors.

Signature formula:

- `message = clientId & apiPath & timestamp & nonce`
- `key = clientId & clientSecret & nonce`
- `sign = base64(HMAC-SHA256(message, key).hex())`

Required headers for POST requests:

- `Content-Type: application/json`
- `client-id`
- `timestamp`
- `nonce`
- `sign`

## Endpoint Selection

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

## Operating Workflow

1. Identify the data type the user actually needs.
2. Select the matching endpoint from the matrix above.
3. Build the JSON body with only required fields.
4. Sign the request with the current timestamp and a 10-digit nonce.
5. Call the API and inspect both HTTP status and JSON `success`.
6. If the response is partial or empty, verify the requested key type, batch size, and endpoint choice before retrying.

## Validation Notes

- Product detail supports SKU or product-name lookup, but not both at once.
- Price requests should be interpreted using the API's own `price`, `exclusivePrice`, and `discountedPrice` fields.
- Shipping responses can include multiple package-level tracking entries per order.
- Saved-products responses are paginated and should be read until all pages are exhausted.

## Helper Script

For direct shell use, see [giga_request.py](scripts/giga_request.py).
Use it for smoke checks and endpoint verification when you need a reproducible signed request.
