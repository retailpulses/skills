# Mercari productVariant Query Reference

## Endpoint

```
POST https://api.mercari-shops.com/v1/graphql
Authorization: Bearer <MERCARI_SHOP_TOKEN>
User-Agent: Inhouse_ERP/1.0.0
```

All production requests must originate from the ConoHa VPS (`160.251.141.110`) via SSH tunnel. See `mercari-shop-api-specialist` skill for SSH setup.

## Primary Query: Look Up Listing by SKU

```graphql
query productVariant($skuCode: ID!) {
  productVariant(by: { skuCode: $skuCode }) {
    id
    skuCode
    stockQuantity
    product {
      id
      name
      description
      price
      status
      imageUrls
      categories {
        id
        name
      }
      shippingPayer
      shippingMethod
      shippingDuration
    }
  }
}
```

### Variables

```json
{"skuCode": "N508P479081B"}
```

### Response Shape

```json
{
  "data": {
    "productVariant": {
      "id": "variant-id",
      "skuCode": "N508P479081B",
      "stockQuantity": 10,
      "product": {
        "id": "product-id",
        "name": "商品名",
        "description": "商品説明",
        "price": 5000,
        "status": "OPENED",
        "imageUrls": ["https://..."],
        "categories": [{"id": "...", "name": "..."}],
        "shippingPayer": "BUYER",
        "shippingMethod": "UNDECIDED",
        "shippingDuration": "ONE_TO_TWO_DAYS"
      }
    }
  }
}
```

### Not Found Response

When a SKU has no listing on the shop, the response includes an `errors` array with a "not found" message:

```json
{
  "errors": [{"message": "productVariant not found"}]
}
```

This is a normal outcome, not an error — it means the product hasn't been listed on that shop yet.

## Minimal Query (Existence Check)

For the listing ID sync, only `product.id` is needed:

```graphql
query productVariant($skuCode: ID!) {
  productVariant(by: { skuCode: $skuCode }) {
    id
    skuCode
    product {
      id
      name
      status
    }
  }
}
```

The `product.id` value is what gets written to Baserow's `Mercari ShopX Product ID` field.

## Key: product.id vs variant.id

- **`productVariant.id`** — the variant-level ID (NOT stored in Baserow)
- **`productVariant.product.id`** — the product-level ID (THIS is what goes into `Mercari ShopX Product ID`)

The backfill plan explicitly states: "Product ID Only — We are backfilling `product.id`, NOT `variant_id`."

## Rate Limiting

- Mercari Shops API does not publish explicit rate limits
- The bulk-updater uses 200ms sleep between calls (`SLEEP_BETWEEN_CALLS = 0.3`)
- The sync-shop3-pricing tool uses 1.0s sleep
- For the listing ID sync, default is 0.3s, configurable via `--interval`

## Shared Client

The canonical Python client is `MercariGraphQLClient` at:
`/Users/user/Documents/Retailpulses/20_REPOS/mercariops/mercari_common/graphql.py`

Usage:
```python
from mercari_common.graphql import MercariGraphQLClient

client = MercariGraphQLClient(token=shop_token, mode="ssh")
resp = client.execute(QUERY, {"skuCode": "N508P479081B"})
```
