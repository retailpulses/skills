---
name: mercari-csv-listing
description: Build a Mercari listing CSV from Item Codes or a GigaB2B Excel file. Listing strategy uses seller-paid shipping (shipping included in price). Data sourced from Supabase baserow_886994_compat_vw (replaces Baserow 886994). Output is a CSV for manual upload via Mercari admin panel.
---

# Mercari Listing CSV

Use when the input is Item Codes or a GigaB2B Excel file and the output is a Mercari listing CSV.

**Listing strategy**: Seller-paid shipping (shipping included in listed price). Data from Supabase `baserow_886994_compat_vw` (product_variants + product_commercials).

## Pipeline

Each key field domain has its own preparation script. The build script is a final CSV assembler that reads already-clean data from Supabase.

```
Step 1: prepare_categories.py
  ├─ Reads product names → keyword-matches category IDs
  ├─ Maps Shops-invalid leaf categories → "その他" variants
  ├─ Writes → Supabase.Mercari category ID
  ↓
Step 2: prepare_colors.py
  ├─ Falls back: Representative_Color_JA empty? → use Main Color → EN→JA translation
  ├─ Writes → Supabase.Representative_Color_JA
  ↓
Step 3: prepare_oversize_images.py
  ├─ Reads Image URLs JSON from Supabase
  ├─ HEAD-checks each URL, downloads >10MB images
  ├─ Resizes to 1500x1500 progressive JPEG, uploads to R2
  ├─ Writes updated R2 URLs → Supabase.Image URLs JSON
  ↓
Step 4: build_mercari_listing_csv.py
  ├─ Reads clean Supabase data → assembles CSV
  ├─ Applies titles, descriptions, scoring
  ↓
Step 5: upload_mercari_csv_to_shops.py
  └─ Uploads CSV to Mercari Shops via SSH
```

## Workflow (execution order)

1. **Prepare categories** — `python3 scripts/prepare_categories.py --item-codes <file> --token <token> [--dry-run]`
   - Matches product names to Mercari Shops category IDs via keyword rules
   - Falls back to "その他" for 7 known Shops-invalid leaf categories
   - Writes `Mercari category ID` to Supabase
2. **Prepare colors** — `python3 scripts/prepare_colors.py --item-codes <file> --token <token> [--dry-run]`
   - Translates `Main Color` (English) → `Representative_Color_JA` (Japanese) for products missing it
   - Uses static EN→JA dict (32 entries) with compound color support (`white+black → ホワイト+ブラック`)
3. **Prepare images** — `python3 scripts/prepare_oversize_images_for_mercari.py --item-codes <file> --r2-public-base-url <url> --token <token> [--dry-run]`
   - Reads `Image URLs JSON` from Supabase, HEAD-checks each URL
   - Downloads oversized images (>10MB), resizes to 1500×1500 progressive JPEG
   - Uploads to R2 bucket `resize-product-images`, writes R2 URLs back to `Image URLs JSON`
4. **Build CSV** — `python3 scripts/build_mercari_listing_csv.py --item-codes <file> --template-csv <template> --shipping-guide-url <url> --token <token> [--score]`
   - Reads clean Supabase data, assembles CSV rows, applies scoring
5. **Upload to Shops** — `python3 scripts/upload_mercari_csv_to_shops.py --csv <output.csv> [--shops shop4] [--mode ssh]`
    - Uploads CSV to Mercari Shops via SSH/VPS

## Hard Gates (build step)

## Prerequisites

- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in env or `.env`.
- `GIGA_CLIENT_ID` and `GIGA_CLIENT_SECRET` for GigaB2B image fetching.
- `R2_PUBLIC_BASE_URL` and `wrangler` CLI for image resize/upload.
- Shipping-fee guide image URL.
- `DEEPSEEK_API_KEY` (optional, for `--use-deepseek-desc`).
- `supabase-py` (pip install supabase) — see `requirements.txt`.

## Data Source

Supabase **`baserow_886994_compat_vw`** — a compatibility view joining `product_variants` + `product_commercials` + `product_mercari_qty_vw`. Exposes the same field names as the old Baserow 886994 table.

## Supabase Access

- Uses `supabase-py` Python client with `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`
- Optional psycopg2 pooler mode for IPv4 access (set `SUPABASE_USE_POOLER=1`)
- Shared module: `scripts/supabase_db.py` — provides `SupabaseDB` class with Baserow-style field name compatibility

## Title Rules

Source: Supabase.`Product Name`.

1. Strip `元SKU` / `元sku` / `元SKU：` patterns from anywhere in the title.
2. Strip leading ASCII SKU codes: `re.sub(r"^[A-Z0-9-]+\s*", "", title)`.
3. Prepend `『数量限定セール』` if discount > 10% (`Discounted Unit Price` vs `Unit Price`).
4. Prepend `『MM/DD再入荷予定』` if `Restock date` is in the future.
5. Cap at 130 chars via hard truncation.

## Description Rules

Source: Supabase.`Product Specification`.

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

**Content**: Raw `Product Specification` text from Supabase, with automatic English→Japanese label translation.

Spec translation applies in two stages:
1. **Label mapping** (always on) — replaces known English labels (e.g. `Weight (kg)`, `Main Material`) with Japanese equivalents using a built-in dictionary. Handles `Label: Value` format line-by-line.
2. **DeepSeek LLM** (optional, via `--use-deepseek-desc`) — passes the full spec through DeepSeek API for a complete natural Japanese translation, overriding the simple label mapping. Requires `DEEPSEEK_API_KEY` env var.

**Footer**: `--description-footer` (default empty).

## Category Rules

**Prepare step**: `prepare_categories.py` keyword-matches product names to Mercari Shops category IDs from a master CSV (2,427 categories). After matching, 7 known Shops-invalid leaf categories are auto-replaced with their parent "その他" (Other) variant:

| Invalid Shops leaf | Replacement |
|---|---|
| スポーツ > マリンスポーツ > サーフィン・ボディボード | スポーツ > マリンスポーツ > その他 |
| ペット用品 > 猫用品 > ベッド・クッション・ハウス | ペット用品 > 猫用品 > その他 |
| フラワー・ガーデニング > 園芸用品 > ガーデンファニチャー | フラワー・ガーデニング > 園芸用品 > その他 |
| ゲーム・おもちゃ・グッズ > おもちゃ > 大型遊具・室内遊具 | ゲーム・おもちゃ・グッズ > おもちゃ > その他 |
| DIY・工具 > 住宅設備 > 物置・車庫 | DIY・工具 > 住宅設備 > その他 |
| 家具・インテリア > ベッド・マットレス > マットレス | 家具・インテリア > ベッド・マットレス > その他 |
| 家具・インテリア > 寝具 > 布団・毛布 | 家具・インテリア > 寝具 > その他 |

## Color Rules

**Prepare step**: `prepare_colors.py` translates `Main Color` (English) → `Representative_Color_JA` (Japanese) for products missing the Japanese color name. Uses a static EN→JA dictionary (32 entries). Compound colors like `white+black` are split and translated as `ホワイト+ブラック`.

## Field Rules

| CSV Column | Source | Rule |
|---|---|---|
| `商品名` | `product_variants.product_name` | SKU-strip → prefixes → hard trim at 130 |
| `商品説明` | `product_variants.product_specification` | Prefix + `【商品説明】` + content + footer |
| `販売価格` | `product_commercials.mercari_effective_price_incl_shipping` | Direct value |
| `SKU1_商品管理コード` | Item Code | Direct |
| `SKU1_種類` | `product_variants.representative_color_ja` | Validated via `is_usable_main_color()`; falls back to Main Color via `prepare_colors.py` |
| `SKU1_在庫数` | `product_mercari_qty_vw.mercari_qty` | Direct |
| `SKU1_現在の在庫数` | `product_mercari_qty_vw.mercari_qty` | Same |
| `カテゴリID` | `product_variants.mercari_category_id` | Direct from Supabase; falls back to `DkjqZAKBXaZN8FB2Kb6zhX` (DIY・工具 > 住宅設備 > その他) if empty |
| `送料ID` | — | Blank (seller-paid) |
| `発送までの日数` | `product_commercials.inventory_status` | `"3"` if `Incoming Stock` (or `More On The Way > 0` or `Estimated Next Arrival Date` set); otherwise `"1"` |
| `商品の状態` | Fixed | `"1"` |
| `配送方法` | Fixed | `"1"` |
| `発送元の地域` | Fixed | `"jp13"` |
| `配送料の負担` | Fixed | `"1"` (SELLER-paid) |
| `商品ステータス` | Quality score | Score >= 80 and no blocking gates → `"2"` (OPENED); else `"1"` (UNOPENED) |

## Image Rules

**Prepare step** (run before build): `prepare_oversize_images_for_mercari.py` resizes images >10MB to 1500×1500 progressive JPEG, uploads to R2, and writes R2 URLs back to `Image URLs JSON`.

**Build step** source: Supabase.`Image URLs JSON` (JSON array). If empty, call GigaB2B API → write back → continue.

Assembly (columns `商品画像名_1` to `商品画像名_20`):
- Fill slots 1–20 sequentially from the image URL list.
- If images < 20: append shipping-fee guide image URL in the last used slot.
- If images >= 20: replace slot 20 with the shipping-fee guide image.
- Cap at 20 slots.

## Hard Exclusion Gates

Rows that fail any hard gate are **excluded from the output CSV entirely** (not just scored as blocked).
Excluded items are reported in the JSON output under `excluded_by_gates`.

| Gate | Condition | Source Field |
|------|-----------|-------------|
| `no_unit_price` | `Unit Price` is null or 0 | Supabase.`Unit Price` |
| `no_fulfillment_fees` | `Unit Fulfillment Fees (Drop Shipping)` is null | Supabase.`Unit Fulfillment Fees (Drop Shipping)` |
| `insufficient_images` | Available images < `--min-image-count` (default 5) | Supabase.`Image URLs JSON` + GigaB2B API fallback |

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | off | Preview exclusions and counts without writing CSV |
| `--min-image-count` | 5 | Minimum required images for a row to be included |
| `--use-deepseek-desc` | off | Use DeepSeek LLM for full spec translation (requires `DEEPSEEK_API_KEY`) |
| `--deepseek-api-key` | env var | DeepSeek API key (checked: `DEEPSEEK_API_KEY` or `Deepseek_API_KEY`) |

In `--dry-run` mode, the script fetches all data and computes gates/scoring but skips writing the CSV, missing-products file, and score file. The JSON report prints normally.

Maximum image count supported by Mercari is 20 (slots `商品画像名_1`–`商品画像名_20`). The shipping-fee guide image occupies the last slot.

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
| `BLOCKED:insufficient_images` | Valid images < `--min-image-count` (default 5) |
| `BLOCKED:no_price` | Price = 0 or empty |
| `BLOCKED:no_unit_price` | `Unit Price` is null or 0 |
| `BLOCKED:no_fulfillment_fees` | `Unit Fulfillment Fees (Drop Shipping)` is null |
| `BLOCKED:hollow_spec` | Product Specification has ≤ 2 meaningful lines (mostly "Not Applicable" filler) |

## Missing Products Report

For input Item Codes not found in Supabase:
- Skip from the listing CSV.
- Output `missing_products_YYYY-MM-DD.csv` listing those codes.

## Output Rules

- Listing CSV: `mercari_listing_YYYY-MM-DD.csv`
- Missing report: `missing_products_YYYY-MM-DD.csv`
- Encoding: `utf-8-sig` (BOM)
- Preserve all template columns; leave `SKU2` through `SKU10` blank
- Verify before delivery

## Error Remediation

| Import error | Cause | Fix |
|---|---|---|
| カテゴリIDの形式または値が正しくありません | Category ID not valid for Mercari Shops (marketplace-only leaf) | Re-run `prepare_categories.py` with the updated "その他" fallback rules |
| 画像データの取得に失敗しました | Images >10MB or inaccessible from Mercari's servers | Run `prepare_oversize_images_for_mercari.py` to resize and rehost on R2 before building CSV |
| SKU1_商品管理コードは既に登録されています | Product already listed in Mercari Shops | Not a bug — skip re-upload for that SKU |

## Upload

Manual via Mercari admin panel (CSV一括機能). This skill does not handle API upload.

## Secrets

- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GIGA_CLIENT_ID`, `GIGA_CLIENT_SECRET` in env or `.env`
- Do not hardcode
