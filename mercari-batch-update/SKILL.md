---
name: mercari-batch-update
description: Batch update existing Mercari listings — price, title, description, and/or category ID — from a CSV file. Supports dry-run, pre-check verification, and batched API mutations with safety guardrails. Use when the user wants to bulk update Mercari product fields, change prices/titles/descriptions/categories across multiple listings, or run a controlled batch mutation against Mercari Shops.
---

# Mercari Batch Update

Batch update existing Mercari Shop listings from a CSV file. Supports **price**, **title**, **description**, and **category ID** — individually or in any combination.

## When To Use

- Bulk price changes across multiple existing listings
- Batch title or description updates
- Category ID corrections or assignments
- Any combination of the above fields in a single run

**Not for:** creating new listings (use `mercari-csv-listing`), image reordering (use `mercari-image-rearrangement`), or image URL backfill (not supported by batch mutation).

## Safety Model

This skill enforces a **validate → dry-run → apply** workflow. The `--confirm` flag acts as a hard gate: you cannot execute live mutations without it.

| Phase | What happens | Mutations? | Command |
|-------|-------------|:---:|---------|
| **validate** | Parse CSV, check columns, detect update types, check token availability, validate field values | No | Automatic |
| **dry-run** | Full pipeline including live SKU→product lookup and price pre-check. Logs exactly what would change per row. | No | `--dry-run` |
| **apply** | Execute `updateProducts` mutations in batches of 20 with rate limiting. Saves per-row results. | **Yes** | `--confirm` |

### Guardrails

- **Dry-run gate**: Running without `--dry-run` or `--confirm` is refused. You must preview first, then explicitly confirm.
- **Price pre-check**: When updating prices WITH a `sku_code` column, the script queries live product data and verifies `old_price` matches the current Mercari price. Mismatches are skipped (likely on TimeSale or already changed).
- **Price updates without SKU**: Blocked by default. If your CSV has no `sku_code`, you must pass `--confirm` to acknowledge the risk of overwriting TimeSale prices without verification.
- **Batch cap**: 20 products per GraphQL mutation (Mercari API limit).
- **Rate limit**: 0.5s default interval between batches (~120/min, well under the ~500/min limit).
- **Idempotency**: Duplicate `product_id` rows are skipped.
- **Results file**: Every run produces a timestamped results CSV with per-row status.

## Quick Start

```bash
# 1. Prepare your CSV (see references/csv-columns.md for accepted columns)
# 2. Always dry-run first
python scripts/mercari_batch_update.py --csv updates.csv --dry-run

# 3. Review the dry-run output, then apply (--confirm is REQUIRED)
python scripts/mercari_batch_update.py --csv updates.csv --confirm
```

## Instructions

### Step 1: Prepare the CSV

Create a CSV with at minimum a `product_id` column (or `Listing ID` / `商品ID`). Add one or more update columns:

- **Price**: `old_price` + `new_price` (both required for price updates) + **`sku_code` strongly recommended** for pre-check
- **Title**: `new_title` or `商品名`
- **Description**: `new_description` or `商品説明`
- **Category ID**: `category_id` or `カテゴリID`
- **Shop** (optional): `Shop`, `shop_name`, or `shop_id` — auto-detected from CSV; use `--shop` to override

Full column reference: `references/csv-columns.md`.

### Step 2: Validate & Dry-Run

```bash
python scripts/mercari_batch_update.py --csv <file.csv> --dry-run
```

The script will:
1. Detect CSV encoding and parse headers
2. Map columns and detect which update types are present
3. Validate field values (prices must be positive numbers, category IDs must be positive integers)
4. If price update: query live Mercari data via SKU lookup and verify `old_price`
5. Print `[DRY-RUN]` lines showing exactly what would change
6. Save a `_dryrun_<ts>.csv` with proposed changes

**Review the dry-run output carefully.** Check for:
- SKIPPED rows (price mismatch, not found, validation errors)
- Correct old→new price changes
- Title/description truncation warnings (>127 chars for title)
- Category ID values

### Step 3: Apply

```bash
python scripts/mercari_batch_update.py --csv <file.csv> --confirm
```

The script:
1. Re-runs validation and pre-check (same as dry-run)
2. Sends `updateProducts` mutations in batches of 20
3. Prints per-batch progress
4. Saves `_results_<ts>.csv` with per-row status: `SUCCESS`, `FAILED_PRODUCT`, `FAILED_BATCH`, `SKIPPED_*`
5. Syncs update timestamp back to Baserow table 938452 (marks `If updated`=True; adds `Price Changed At` only if price was part of the update)

### Step 4: Verify

- Check the results CSV for any FAILED rows
- Spot-check a few listings on Mercari Shop admin
- Re-run with `--dry-run` to confirm no remaining diffs

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--csv` | (required) | Path to input CSV |
| `--dry-run` | off | Preview changes without executing mutations |
| `--confirm` | off | **Required** for live execution. Bypasses dry-run gate and price-without-SKU guard |
| `--shop` | auto-detected | Force a single shop (`shop1`–`shop4`); overrides CSV shop column |
| `--interval` | 0.5 | Seconds between batches |

## CSV Examples

### Price-only update
```csv
product_id,sku_code,old_price,new_price
m123456,SKU-001,2800,3200
m789012,SKU-002,1500,1200
```

### Title + Description update
```csv
product_id,new_title,商品説明
m123456,【新品】ウィジェット Pro,高品質ウィジェットです。送料無料。
```

### Category ID update
```csv
product_id,category_id
m123456,1234
m789012,5678
```

### Combined (price + title + category)
```csv
product_id,sku_code,old_price,new_price,new_title,category_id
m123456,SKU-001,2800,3200,【値下げ】ウィジェット Pro,1234
```

## Requirements

- Python 3.9+
- Access to `mercari_common` package (GraphQL client, token resolver, shop config)
- Access to `baserow_client` package (for Baserow sync)
- Environment variables: Mercari shop tokens (`MERCARI_SHOP1_TOKEN`–`MERCARI_SHOP4_TOKEN`) and optionally `BASEROW_TOKEN`
- The `mercari_batch_update.py` script must be runnable from the skill directory or with the project's Python path configured

## Integration

This skill delegates API-level concerns to `mercari-shop-api-specialist`:
- Token resolution and shop configuration
- GraphQL mutation shapes (`updateProduct` / `updateProducts`)
- VPS SSH path for production execution (when applicable)
- Rate limiting and error interpretation

For SSH/VPS-based execution, see `mercari-shop-api-specialist` for connection details.

## Best Practices

1. **Always dry-run first.** The script enforces this: you cannot apply without `--confirm`.
2. **Start small.** Test with 2–3 products before running a full CSV.
3. **Keep the CSV.** The results file references your input; keep both for audit.
4. **Always include SKU with price updates.** Without `sku_code`, price pre-check is impossible and the script will refuse unless you pass `--confirm` to acknowledge the risk.
5. **Title length.** Mercari titles max out at ~127 characters. The script auto-truncates.
6. **Category IDs are integers.** Validate them against the Mercari category tree before uploading. Use `mercari-category-id` to look up correct IDs.
7. **Shop detection.** If your CSV has a `Shop` column, the script auto-detects it. Rows for different shops must be in separate CSVs.
