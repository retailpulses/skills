---
name: mercari-listing-id-sync
description: Sync Mercari Shop listing IDs back to Baserow Products table 886994. Two modes — Discovery (scan Baserow SKUs lacking a Mercari Product ID, query Mercari API by skuCode to find them, write back product.id) and Capture (write known item_code→product_id pairs from CSV or CLI args). Idempotent, dry-run capable, per-shop targeting. Use when the user wants to backfill Mercari listing IDs, find newly listed products on a Mercari shop, or capture listing IDs after CSV upload.
---

# Mercari Listing ID Sync

Sync Mercari Shop listing `product.id` values back to the Baserow Products table, mapping by `skuCode` (Mercari) ↔ `item code` (Baserow).

## When To Use

- Backfill Mercari listing IDs for products that were listed before the ID fields existed
- Discover which Baserow products have live Mercari listings on a given shop
- Capture listing IDs after a CSV upload or bulk listing operation
- Periodic audit: check for listings that exist on Mercari but aren't tracked in Baserow

## Modes

### Discovery Mode (Default)

Find products listed on a Mercari shop by checking Baserow SKUs against the Mercari API:

1. Fetch all rows from Baserow Products (886994) where `item code` is set but `Mercari ShopX Product ID` is empty
2. For each candidate, query Mercari's `productVariant(by: { skuCode })` via SSH tunnel through ConoHa VPS
3. If a listing is found, record the `product.id` → `item code` mapping
4. If not found, skip (the product hasn't been listed on that shop)
5. Batch-update Baserow with the discovered IDs (chunks of 100)

### Capture Mode (`--from-csv` or `--item-codes`)

Write known `{item_code, product_id}` mappings directly to Baserow without querying Mercari:

- `--from-csv mappings.csv` — read a CSV with `item_code` and `mercari_product_id` columns
- `--item-codes "SKU1,SKU2" --product-ids "m123,m456"` — pass explicit pairs

Both modes are idempotent: rows that already have a value in the target field are skipped.

## Usage

```bash
# Discovery mode — preview what would be written
python3 tools/mercari-listing-id-sync/sync_mercari_listing_ids.py \
  --shop shop1 --dry-run --max-skus 5

# Discovery mode — live execution
python3 tools/mercari-listing-id-sync/sync_mercari_listing_ids.py \
  --shop shop1 --confirm

# Discovery mode — limit scope
python3 tools/mercari-listing-id-sync/sync_mercari_listing_ids.py \
  --shop shop2 --confirm --max-skus 50

# Capture mode — from CSV
python3 tools/mercari-listing-id-sync/sync_mercari_listing_ids.py \
  --shop shop1 --confirm --from-csv shop1_listing_ids.csv

# Capture mode — explicit item codes
python3 tools/mercari-listing-id-sync/sync_mercari_listing_ids.py \
  --shop shop3 --confirm --item-codes "N508P479081B,N508P479082C"

# Save reports
python3 tools/mercari-listing-id-sync/sync_mercari_listing_ids.py \
  --shop shop1 --confirm --report-dir ./reports
```

## Shop → Field Mapping

| `--shop` | Mercari Shop ID | Baserow Field | Field ID |
|----------|----------------|---------------|----------|
| `shop1` | `WMyisFmhbGWyVAPEwsfirn` | `Mercari Shop1 Product ID` | 8335204 |
| `shop2` | `ZaMyGWzp6hUdgDh5E9ADob` | `Mercari Shop2 Product ID` | 8335205 |
| `shop3` | `2JGrmZqojnBMfdWrtP2xk3` | `Mercari Shop3 Product ID` | 8335206 |
| `shop4` | `2JMLHBxjiFHDr55jMwA7fs` | `Mercari Shop4 Product ID` | 8332941 |

## Safety Rules

1. **VPS mandatory for production** — All Mercari API calls go through ConoHa VPS SSH tunnel (`root@160.251.141.110`)
2. **Dry-run first** — Always run with `--dry-run` before `--confirm`
3. **`--confirm` required** — Live execution fails without it
4. **Idempotent by default** — Only writes to rows where the target field is currently empty
5. **No row creation** — This skill updates existing Products rows only; it never creates new rows
6. **`product.id` only** — Writes the Mercari `product.id`, not `variant.id`
7. **Rate limiting** — Default 0.3s between Mercari API calls; configurable via `--interval`

## Credentials

Resolved from environment (or `.env` file in the mercariops repo root):

| Variable | Purpose |
|----------|---------|
| `BASEROW_TOKEN` | Baserow API token (database token) |
| `MERCARI_SHOP1_TOKEN` | Mercari Shop1 API bearer token |
| `MERCARI_SHOP2_TOKEN` | Mercari Shop2 API bearer token |
| `MERCARI_SHOP3_TOKEN` | Mercari Shop3 API bearer token |
| `MERCARI_SHOP4_TOKEN` | Mercari Shop4 API bearer token |

Optional:
- `BASEROW_BASE_URL` — default `https://api.baserow.io`
- `MERCARI_VPS_HOST` — default `160.251.141.110`
- `MERCARI_SSH_KEY` — default `~/.ssh/id_ed25519`

## Implementation

The canonical script lives in the `mercariops` repo:

- **Script**: `tools/mercari-listing-id-sync/sync_mercari_listing_ids.py`
- **Shared libs**: `mercari_common/graphql.py` (MercariGraphQLClient), `baserow_client/client.py` (BaserowClient)

## Related Skills

- **`mercari-shop-api-specialist`** — Mercari GraphQL API patterns, SSH tunnel setup, token resolution
- **`baserow-database-manager`** — Baserow CRUD, schema management, batch operations
- **`mercari-csv-listing`** — CSV-based Mercari listing creation (Capture mode pairs with this: list via CSV, then capture the resulting product IDs)

## References

- `references/MERCARI_PRODUCTVARIANT_API.md` — GraphQL query shapes for `productVariant`
- `references/PRODUCTS_TABLE_FIELDS.md` — Baserow table 886994 Mercari ID field details
- `/Users/user/Documents/Retailpulses/20_REPOS/CatalogSync/docs/plans/MASTER_WORK_PLAN_MERCARI_ID_BACKFILL.md` — Original backfill plan with field IDs and safety rules
