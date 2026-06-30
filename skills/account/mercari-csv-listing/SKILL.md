---
name: mercari-csv-listing
description: [DEPRECATED] Build a Mercari listing CSV from Item Codes or a GigaB2B Excel file. Use canonical version at 20_REPOS/mercariops/skills/mercari-csv-listing/ instead.
---

# [DEPRECATED] Mercari Listing CSV

> **This copy is deprecated.** The canonical version is maintained at:
> **`20_REPOS/mercariops/skills/mercari-csv-listing/`**

Use when the input is Item Codes or a GigaB2B Excel file and the output is a Mercari listing CSV.

**Listing strategy**: Seller-paid shipping (shipping included in listed price). All data from Baserow table 886994 (Products).

## Workflow

1. Deduplicate item codes or parse Excel.
2. Check each Item Code against Baserow 886994. Skip missing codes; at the end, output `missing_products_YYYY-MM-DD.csv`.
3. Resolve image URLs from 886994.`Image URLs JSON`. If empty, fetch from GigaB2B API and backfill.
4. Generate title from 886994.`Product Name` (SKU-strip, prefixes, hard trim at 130).
5. Generate description from 886994.`Product Specification` + prefix boilerplate.
6. Score listing quality (10-module, 100-point rubric). If score >= 80 and no blocking gates → `商品ステータス = "2"` (OPENED). Otherwise `"1"` (UNOPENED).
7. Assemble one CSV row per existing Item Code.
8. User uploads CSV manually via Mercari admin panel (CSV一括機能).

## Prerequisites

- `BASEROW_TOKEN` in env or `.env`.
- `GIGA_CLIENT_ID` and `GIGA_CLIENT_SECRET` for GigaB2B image fetching.
- Shipping-fee guide image URL.

## Data Source

Single table: **886994** (Products). No other Baserow tables are used.

## Baserow Access

- `Authorization: Token <token>`
- `user_field_names=true`
- `size=200&page=<n>` for pagination

## Title Rules

Source: 886994.`Product Name`.

1. Strip SKU prefix: `re.sub(r"^[A-Z0-9-]+\s*", "", title)`.
2. Prepend `数量限定セール` if discount > 10% (`Discounted Unit Price` vs `Unit Price`).
3. Prepend `MM/DD再入荷予定` if `Restock date` is in the future.
4. Cap at 130 chars via hard truncation.

## Description Rules

Source: 886994.`Product Specification`.

Structure:
```
[prefix boilerplate]

【商品説明】

[content]

[footer]
```

**Prefix** (default, overridable via `--description-prefix`):
```
ホムブリスショップへようこそ
♪すべての商品は未開封の新品です
♪フォロー割あり
♪まとめ買い割あり：2点で2%OFF、3点で3%OFF、最大5%（一部商品適用外）
♪発送と送料：在庫品は1～2営業日以内に発送、再入荷商品は入荷後1～2営業日以内に発送いたします。北海道は基本的に追加送料不要です。沖縄への送料は別途お見積りが必須です。
```

**Content**: Raw `Product Specification` text from Baserow.

**Footer**: `--description-footer` (default empty).

## Field Rules

| CSV Column | Source | Rule |
|---|---|---|
| `商品名` | 886994.`Product Name` | SKU-strip → prefixes → hard trim at 130 |
| `商品説明` | 886994.`Product Specification` | Prefix + `【商品説明】` + content + footer |
| `販売価格` | 886994.`Mercari Effective Pricing (incl. shipping)` | Direct value |
| `SKU1_商品管理コード` | Item Code | Direct |
| `SKU1_種類` | 886994.`Representative_Color_JA` | Validated via `is_usable_main_color()`; blank if invalid |
| `SKU1_在庫数` | 886994.`Mercari Qty` | Direct |
| `SKU1_現在の在庫数` | 886994.`Mercari Qty` | Same |
| `カテゴリID` | 886994.`Mercari category ID` | Direct from Baserow; blank if empty |
| `送料ID` | — | Blank (seller-paid) |
| `発送までの日数` | 886994.`Inventory Status` | `"3"` if `Incoming Stock` (or `More On The Way > 0` or `Estimated Next Arrival Date` set); otherwise `"1"` |
| `商品の状態` | Fixed | `"1"` |
| `配送方法` | Fixed | `"1"` |
| `発送元の地域` | Fixed | `"jp13"` |
| `配送料の負担` | Fixed | `"1"` (SELLER-paid) |
| `商品ステータス` | Quality score | Score >= 80 and no blocking gates → `"2"` (OPENED); else `"1"` (UNOPENED) |

## Image Rules

Source: 886994.`Image URLs JSON` (JSON array). If empty, call GigaB2B API → write back → continue.

Assembly (columns `商品画像名_1` to `商品画像名_20`):
- Fill slots 1–20 sequentially from the image URL list.
- If images < 20: append shipping-fee guide image URL in the last used slot.
- If images >= 20: replace slot 20 with the shipping-fee guide image.
- Cap at 20 slots.

## Listing Quality Scoring

10-module, 100-point rubric. Threshold: **>= 80 → `"2"` (OPENED)**, else `"1"` (UNOPENED).

All checks use data available from 886994 at CSV build time. No section-structure pattern matching.

### 1. Title Completeness (14 pts)

| Condition | Points |
|---|---|
| Title empty | 0 (BLOCKED) |
| < 80 chars | 2 |
| 80–99 chars | 8 |
| 100–130 chars | 14 |
| > 130 chars (post-trim) | 0 (BLOCKED) |
| Contains core product noun (家具/ベッド/チェア/テーブル/収納/ラック/ソファ/デスク/キャビネット/マットレス/スツール/棚/机) | Required; if absent, max 4 |
| Contains dimension keywords (cm/mm/幅/奥行/高さ) | +2 bonus (capped at 14) |

### 2. Description Quality (14 pts)

| Condition | Points |
|---|---|
| Description empty | 0 (BLOCKED) |
| < 500 chars | 2 |
| 500–1199 chars | 6 |
| 1200–1999 chars | 10 |
| 2000–3000 chars | 14 |
| > 3000 chars | 0 (BLOCKED) |
| `・` bullets >= 3 | +2 bonus (capped at 14) |

### 3. Image Count (14 pts)

| Condition | Points |
|---|---|
| 0 valid images | 0 (BLOCKED) |
| 1–2 images | 4 |
| 3–6 images | 8 |
| 7–9 images | 11 |
| 10–14 images | 13 |
| 15–20 images | 14 |

### 4. Category ID (12 pts)

| Condition | Points |
|---|---|
| `Mercari category ID` empty after resolution | 0 |
| Resolved and non-empty | 12 |

### 5. Pricing (12 pts)

| Condition | Points |
|---|---|
| `Mercari Effective Pricing (incl. shipping)` = 0 or empty | 0 (BLOCKED) |
| 1–999 JPY | 4 |
| 1000–4999 JPY | 8 |
| 5000+ JPY | 12 |

### 6. Variant Name (`SKU1_種類`) (8 pts)

| Condition | Points |
|---|---|
| Empty / invalid | 0 |
| Valid `Representative_Color_JA` present | 8 |

### 7. Inventory & Dispatch Clarity (8 pts)

| Condition | Points |
|---|---|
| `Mercari Qty` = 0 | 0 |
| `Mercari Qty` >= 1 and `Inventory Status` != Incoming Stock | 8 |
| `Mercari Qty` >= 1 and `Inventory Status` = Incoming Stock | 6 |

### 8. Shipping Fee Guide Image (6 pts)

| Condition | Points |
|---|---|
| Shipping-fee guide image appended in image slots | 6 |
| Not present | 0 |

### 9. Discount / Urgency Signals (6 pts)

| Condition | Points |
|---|---|
| Discount > 0% (`Discounted Unit Price` < `Unit Price`) | 4 |
| Discount > 10% | 6 |
| No discount | 2 |

### 10. Product Specification Length (6 pts)

| Condition | Points |
|---|---|
| `Product Specification` empty | 0 |
| < 200 chars | 2 |
| 200–799 chars | 4 |
| 800+ chars | 6 |

### Blocking Gates

If any gate is triggered, score = 0 and `商品ステータス` = `"1"` regardless of module total.

| Gate | Condition |
|---|---|
| `BLOCKED:no_title` | Title empty or > 130 chars |
| `BLOCKED:no_description` | Description empty or > 3000 chars |
| `BLOCKED:no_images` | 0 valid images |
| `BLOCKED:no_price` | Price = 0 or empty |

## Missing Products Report

For input Item Codes not found in Baserow 886994:
- Skip from the listing CSV.
- Output `missing_products_YYYY-MM-DD.csv` listing those codes.

## Output Rules

- Listing CSV: `mercari_listing_YYYY-MM-DD.csv`
- Missing report: `missing_products_YYYY-MM-DD.csv`
- Encoding: `utf-8-sig` (BOM)
- Preserve all template columns; leave `SKU2` through `SKU10` blank
- Verify before delivery

## Upload

Manual via Mercari admin panel (CSV一括機能). This skill does not handle API upload.

## Secrets

- `BASEROW_TOKEN`, `GIGA_CLIENT_ID`, `GIGA_CLIENT_SECRET` in env or `.env`
- Do not hardcode
