# Mercari Variant API Notes

## API Limitation

**Variants cannot be added to an existing Mercari product via API.** The `UpdateProductInput` type (18 fields, confirmed by live schema introspection 2026-05-24) does NOT include a `variants` field.

### Available Mutations

| Mutation | Variant Support |
|----------|:---:|
| `createProduct` | ✅ Sets initial variant list |
| `updateProduct` | ❌ No `variants` field |
| `updateProductVariants` | ⚠️ Updates existing variant properties only (stock, name) |

### updateProductVariants

```graphql
mutation updateProductVariants($inputs: [UpdateProductVariantsInput!]!) {
  updateProductVariants(inputs: $inputs) {
    productVariants { id skuCode stockQuantity product { id status } }
  }
}
```

Input shape:
```json
{"inputs": [{"by": {"skuCode": "..."}, "input": {"stockQuantity": 10, "name": "カラー名"}}]}
```

Supports: `stockQuantity`, `name`. Does NOT support adding new SKUs.

## Product Model

```
Product (listing)
├── id, name, description, price, status, condition, categoryId
├── imageUrls[], shippingPayer, shippingMethod, shippingDuration,
│   shippingFromStateId, shippingConfigurationId
└── variants[]
    ├── variant { id, skuCode, stockQuantity, name? }
    ├── variant { ... }
    └── ... (max 10)
```

## CreateProductInput Fields

From the production `build_create_input()` in `upload_mercari_csv_to_shops.py`:

| Field | Required | Example |
|-------|:---:|---------|
| `categoryId` | Yes | `"oaRD8SorG7tSgWWrME7Nz5"` |
| `condition` | Yes | `"BRAND_NEW"` |
| `description` | Yes | max 2000 chars |
| `imageUrls` | Yes | `["https://..."]` (max 20) |
| `name` | Yes | max 120 chars |
| `price` | Yes | integer (JPY) |
| `shippingDuration` | Yes | `"ONE_TO_TWO_DAYS"` |
| `shippingFromStateId` | Yes | `"jp13"` (Tokyo) |
| `shippingMethod` | Yes | `"UNDECIDED"` |
| `shippingPayer` | Yes | `"SELLER"` (送料込み) or `"BUYER"` (送料別) |
| `shippingConfigurationId` | No* | Required when `shippingPayer=BUYER` |
| `status` | Yes | `"UNOPENED"`, `"OPENED"` |
| `variants` | Yes | `[{skuCode, stockQuantity, name?}]` (max 10) |
| `brandId` | No | Brand identifier |
| `productPreOrder` | No | Pre-order settings |

## Shop Configuration

| Shop | Shop ID | Token Env Var |
|------|---------|---------------|
| shop1 | `WMyisFmhbGWyVAPEwsfirn` | `MERCARI_SHOP1_TOKEN` |
| shop2 | `ZaMyGWzp6hUdgDh5E9ADob` | `MERCARI_SHOP2_TOKEN` |
| shop3 | `2JGrmZqojnBMfdWrtP2xk3` | `MERCARI_SHOP3_TOKEN` |
| shop4 | `2JMLHBxjiFHDr55jMwA7fs` | `MERCARI_SHOP4_TOKEN` |

## VPS Connection

- Host: `root@160.251.141.110`
- SSH Key: `~/.ssh/id_ed25519`
- Force IPv4: `curl -4`
- Endpoint: `https://api.mercari-shops.com/v1/graphql`
- User-Agent: `Inhouse_ERP/1.0.0`
