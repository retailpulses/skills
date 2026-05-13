# Mercari API Upload to 4 Shops (Skip Existing)

## Goal

Upload the final Mercari CSV to multiple shops by API using `createProduct`, while skipping already-existing SKUs in each shop.

## Mandatory dedupe rule

For each `SKU1_商品管理コード` and each shop:

1. Query `productVariant(by: { skuCode })` first.
2. If found, skip create.
3. If not found, call `createProduct`.
4. Verify again by `skuCode` after create, even when create returns errors.
5. Set the created variant name from `SKU1_種類` when available; do not hardcode `Default`. If `SKU1_種類` is blank, omit the variant name instead of inventing one.

## Runtime rules

- Default execution mode is `ssh` (Conoha VPS + IPv4) per production SOP.
- Use `User-Agent: Inhouse_ERP/<VERSION>`.
- Keep tokens only in env vars, not in command history or docs.

## Required env vars

- `MERCARI_SHOP1_TOKEN`
- `MERCARI_SHOP2_TOKEN`
- `MERCARI_SHOP3_TOKEN`
- `MERCARI_SHOP4_TOKEN`

## Dry run

```bash
python3 scripts/upload_mercari_csv_to_shops.py \
  --csv "/path/to/mercari_listing_YYYY-MM-DD.csv" \
  --shops "shop1,shop2,shop3,shop4" \
  --mode ssh \
  --dry-run
```

## Production run

```bash
python3 scripts/upload_mercari_csv_to_shops.py \
  --csv "/path/to/mercari_listing_YYYY-MM-DD.csv" \
  --shops "shop1,shop2,shop3,shop4" \
  --mode ssh
```

## Output

The script writes a JSON execution report with per-row, per-shop status:

- `skipped_existing`
- `created_or_exists_after_create`
- `invalid`
- `failed`
