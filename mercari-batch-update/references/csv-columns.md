# CSV Column Reference

All accepted column names for the Mercari batch update CSV. Column names are case-sensitive and trimmed of whitespace.

## Identity Columns (at least one required)

| CSV Header | Internal Key | Required | Notes |
|------------|-------------|:---:|-------|
| `product_id` | `product_id` | ✅ | Mercari product ID (e.g., `m123456`) |
| `Listing ID` | `product_id` | ✅ | Same as above (Baserow convention) |
| `商品ID` | `product_id` | ✅ | Japanese header variant |

## SKU Column (required for price pre-check, strongly recommended for price updates)

| CSV Header | Internal Key | Required | Notes |
|------------|-------------|:---:|-------|
| `Item Code (SKU)` | `sku_code` | For price pre-check | Used for live SKU→product lookup and price verification |
| `SKU` | `sku_code` | For price pre-check | Short alias |
| `sku_code` | `sku_code` | For price pre-check | Direct key |
| `商品管理番号` | `sku_code` | For price pre-check | Japanese header variant |

**Important:** If you omit `sku_code` from a price-update CSV, the script refuses to run unless you pass `--confirm`. Without SKU, live price pre-check is impossible — you risk overwriting TimeSale prices or externally changed prices.

## Price Columns (both required for price updates)

| CSV Header | Internal Key | Required | Notes |
|------------|-------------|:---:|-------|
| `Current Prod Price` | `old_price` | For price | Current live price for pre-check verification |
| `old_price` | `old_price` | For price | Direct key |
| `現在価格` | `old_price` | For price | Japanese header variant |
| `NEW Prod Price` | `new_price` | For price | Target price to set |
| `new_price` | `new_price` | For price | Direct key |
| `販売価格` | `new_price` | For price | Japanese header variant |

## Title Column

| CSV Header | Internal Key | Required | Notes |
|------------|-------------|:---:|-------|
| `商品名` | `new_title` | For title | Japanese header (primary) |
| `proposed_title` | `new_title` | For title | GigaB2B convention |
| `new_title` | `new_title` | For title | Direct key |
| `タイトル` | `new_title` | For title | Japanese alternate |

Title max length: ~127 characters. The script auto-truncates longer values.

## Description Column

| CSV Header | Internal Key | Required | Notes |
|------------|-------------|:---:|-------|
| `商品説明` | `new_description` | For desc | Japanese header (primary) |
| `new_description` | `new_description` | For desc | Direct key |
| `説明` | `new_description` | For desc | Japanese alternate (ambiguous — prefer 商品説明) |

## Category ID Column (NEW)

| CSV Header | Internal Key | Required | Notes |
|------------|-------------|:---:|-------|
| `category_id` | `category_id` | For category | Direct key |
| `カテゴリID` | `category_id` | For category | Japanese header |
| `Mercari category ID` | `category_id` | For category | Baserow convention |

Category ID must be a positive integer. Use `mercari-category-id` skill to look up valid category IDs before populating this column.

## Shop Column (optional)

| CSV Header | Internal Key | Required | Notes |
|------------|-------------|:---:|-------|
| `shop_name` | `shop_name` | No | e.g., `Shop3` |
| `Shop` | `shop_name` | No | Short alias |
| `ショップ` | `shop_name` | No | Japanese header variant |
| `shop_id` | `shop_id` | No | Numeric shop ID (resolved to name) |
| `Shop ID` | `shop_id` | No | Alternate header |

If no shop column is present, defaults to `Shop3`. Use `--shop` CLI flag to override all rows to a single shop. Multi-shop CSVs are rejected — split into separate CSVs per shop.

## Example CSVs

### Minimal price update
```csv
product_id,sku_code,old_price,new_price
m123456,SKU-001,2800,3200
m789012,SKU-002,1500,1200
```

### Title + description (no price pre-check)
```csv
商品ID,商品名,商品説明
m123456,【新品】ウィジェット Pro,高品質ウィジェットです。
m789012,【美品】ガジェット Lite,コンパクトで軽量。
```

### Category ID update only
```csv
product_id,category_id
m123456,1234
m789012,5678
```

### Full combined update
```csv
Listing ID,Item Code (SKU),Current Prod Price,NEW Prod Price,商品名,商品説明,カテゴリID
m123456,SKU-001,2800,3200,【値下げ】ウィジェット Pro,高品質ウィジェット,1234
m789012,SKU-002,1500,1200,【セール】ガジェット Lite,軽量コンパクト,5678
```
