# GigaB2B OpenAPI Access Reference

## Base URL

- Default: `https://openapi.gigab2b.com`
- Use the sandbox only if the user explicitly asks for it.

## Common Request Shape

Headers:

- `Content-Type: application/json`
- `client-id`
- `timestamp`
- `nonce`
- `sign`

Signing:

- `message = clientId & apiPath & timestamp & nonce`
- `key = clientId & clientSecret & nonce`
- `sign = base64(HMAC-SHA256(message, key).hex())`

Nonce:

- Use a 10-digit random numeric string.

Timestamp:

- Use milliseconds since Unix epoch.
- Keep the request within the API's allowed freshness window.

## Endpoint Matrix

### Saved products

- `POST /b2b-overseas-api/v1/buyer/product/skus/v1`
- Use for saved-product syncs, audits, and recent-window discovery.
- Typical body fields:
  - `page`
  - `pageSize`
  - `sort`
  - `queryTimeType`
  - `startTime`
  - `endTime`

### Product detail

- `POST /b2b-overseas-api/v1/buyer/product/detailInfo/v1`
- Use for description, images, dimensions, attributes, and availability.
- Body:
  - exactly one of `skus` or `productNames`
  - max 200 entries

### Price

- `POST /b2b-overseas-api/v1/buyer/product/price/v1`
- Use for pricing fields such as `price`, `exclusivePrice`, and `discountedPrice`.
- Body:
  - `skus`
  - max 200 entries

### Shipping

- `POST /b2b-overseas-api/v1/buyer/order/track-no/v1`
- Use for tracking numbers and carrier details.
- Body:
  - `orderNo`
  - max 100 entries

## Endpoint Choice Heuristics

- Need metadata about a product: use product detail.
- Need current pricing values: use price.
- Need package tracking or carrier names: use shipping.
- Need the user's saved catalog footprint: use saved-products.

## Response Handling

- Check HTTP status and body `success`.
- Treat empty or null fields as real API output unless a later endpoint proves otherwise.
- Keep batch sizes small when validating new assumptions.
- Re-read only the records or SKUs that changed.
