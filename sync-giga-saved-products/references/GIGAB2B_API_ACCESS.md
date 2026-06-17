# GIGAB2B API Access

This skill follows the repo's working GigaB2B access pattern for the sync workflow.

## Saved-Products API

- Base URL: `https://openapi.gigab2b.com`
- Endpoint: `POST /b2b-overseas-api/v1/buyer/product/skus/v1`
- Purpose: fetch the user's saved products / collection list
- Time filter mode for "recent 30 days":
  - `queryTimeType = 2`
  - `startTime` and `endTime` define the window

## Request Shape

- Headers:
  - `client-id`
  - `timestamp`
  - `nonce`
  - `sign`
  - `Content-Type: application/json`
- Body fields:
  - `page`
  - `pageSize`
  - `sort`
  - `firstArrivalDate`
  - `lastUpdatedAfter`
  - `queryTimeType`
  - `startTime`
  - `endTime`
- Response fields used by this skill:
  - `data.records[].sku`
  - `data.records[].productName`
  - `data.records[].updateTime`
  - `data.records[].firstArrivalDate`
  - `data.records[].addedTime`

## Signature Rule

- `message = clientId & apiPath & timestamp & nonce`
- `key = clientId & clientSecret & nonce`
- `sign = base64(HMAC-SHA256(message, key).hex())`

## Operational Note

The sync workflow should use this saved-products API directly. The older OAuth inventory/price flow in the repo is unrelated to this skill and should not be used as the primary path for saved-product sync.
