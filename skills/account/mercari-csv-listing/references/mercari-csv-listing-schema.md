# Mercari CSV Listing Schema Reference

## Live Baserow Sources

- `912520` `Product info pack`
  - Product identity, images, dimensions, description fragments, category signal, `Mercari category ID`
- `886994` `Products`
  - `Mercari ref pricing`, `Mercari Qty`, `Discount%`, `Restock date`, `Unit Fulfillment Fee (Drop Shipping)`, `Mercari category ID`
- `912536` `Copywriting`
  - Mercari title and description source
- `914491`
  - Shipping bracket lookup by `Lower end` / `Upper end` -> `Shipping ID`

## Mercari Copy Source

- If `912536` has a Mercari row for the `Item Code`, use it.
- If not, generate it with `giga-resource-pack-copywriting` before building the CSV.
- Use the Mercari title as `商品名`.
- Use the Mercari description as `商品説明`.

## Title Prefix Rules

- Compute the effective discount from `886994` by comparing `Discounted Unit Price` or `Exclusive Price` against `Unit Price`.
- If the effective discount is greater than `10%`, prepend `数量限定セール`.
- If a future `Restock date` exists, prepend `MM/DD再入荷予定`.
- If both conditions apply, keep both prefixes in the final title.

## CSV Column Conventions

### Required / primary fields

- `商品名`
- `商品説明`
- `SKU1_商品管理コード`
- `SKU1_種類` (use `886994.Main Color (JP)` only; if blank, leave the field blank / `NULL`)
- `販売価格`
- `SKU1_現在の在庫数`
- `カテゴリID`
- `送料ID`

### Fixed defaults

- `商品の状態 = 1`
- `配送方法 = 1`
- `発送元の地域 = jp13`
- `発送までの日数 = 5` when product is in pre-sale status (`Mercari Qty = 5`), otherwise `1`
- `商品ステータス = 2`
- `配送料の負担 = 2`; the upload/update layer maps this workflow to buyer-paid shipping (`BUYER`) when `送料ID` is being applied

## Shipping Update Rule

- For existing Mercari product updates, `shippingConfigurationId` is only accepted when `shippingPayer=BUYER`.
- If `shippingPayer=SELLER`, Mercari rejects the shipping config update with `request parameter is invalid`.

### Image columns

- Preserve the current template order for:
  - `商品画像名_1..20`
  - `商品画像更新フラグ_1..20`
  - `商品画像登録有無_1..20`
- Fill the image-name columns from `912520` image URLs in source order.
- Fill up to `商品画像名_20`.
- Always reserve the last filled image slot for the shipping-fee guide image:
  - if the product has fewer than 20 images, append the guide image after the last source image
  - if the product has 20 or more images, replace image slot 20 with the guide image
- Preserve the template's image flag pattern unless explicitly instructed otherwise.

### Unused columns

- Leave `SKU2` to `SKU10` blank.
- Leave `商品画面用タイトル` and `商品省略名` blank unless the user explicitly asks for them.
- Leave any other unspecified columns blank unless the current live template requires them.
