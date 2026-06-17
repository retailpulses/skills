# Baserow Products Table — Mercari Listing ID Fields

## Table

- **Database**: Homebliss ERP MVP (`393156`)
- **Table**: Products (`886994`)
- **Primary Key Field**: `item code` (text, lowercase with space)

## Mercari ShopX Product ID Fields

These four text fields hold the Mercari `product.id` for each shop's listing of a product. The mapping key is `item code` (Baserow) ↔ `skuCode` (Mercari GraphQL `productVariant`).

| Shop Key | Baserow Field Name | Field ID | Mercari Shop ID |
|----------|-------------------|----------|-----------------|
| `shop1` | `Mercari Shop1 Product ID` | `8335204` | `WMyisFmhbGWyVAPEwsfirn` |
| `shop2` | `Mercari Shop2 Product ID` | `8335205` | `ZaMyGWzp6hUdgDh5E9ADob` |
| `shop3` | `Mercari Shop3 Product ID` | `8335206` | `2JGrmZqojnBMfdWrtP2xk3` |
| `shop4` | `Mercari Shop4 Product ID` | `8332941` | `2JMLHBxjiFHDr55jMwA7fs` |

## Writing to These Fields

### Single Row Update

```
PATCH /api/database/rows/table/886994/{row_id}/?user_field_names=true
Authorization: Token <BASEROW_TOKEN>
Content-Type: application/json

{"Mercari Shop1 Product ID": "m1234567890"}
```

### Batch Update (Max 100 Items)

```
PATCH /api/database/rows/table/886994/batch/?user_field_names=true
Authorization: Token <BASEROW_TOKEN>
Content-Type: application/json

{"items": [
  {"id": 123, "Mercari Shop1 Product ID": "m1234567890"},
  {"id": 456, "Mercari Shop1 Product ID": "m0987654321"}
]}
```

## Idempotency

- **Write only to rows where the target field is empty.** If a row already has a `Mercari ShopX Product ID`, skip it (unless `--overwrite` is explicitly passed).
- This makes repeated runs safe — only newly discovered listings get written.

## Candidate Query (Discovery Mode)

For efficient candidate fetching, use Baserow's server-side blank filter:

```
GET /api/database/rows/table/886994/?user_field_names=true&size=200&filter__field_8335204__is_blank=true
```

This returns only rows where the shop's field is empty. Combined with client-side filtering for non-empty `item code`, this gives the exact candidate set.

## BaserowClient

The canonical Python client is `BaserowClient` at:
`/Users/user/Documents/Retailpulses/20_REPOS/mercariops/baserow_client/client.py`

Key methods used by the sync:
- `fetch_all_rows(table_id)` — full table scan with pagination
- `fetch_rows_by_filter(table_id, field_key, values, operator)` — server-side filtered fetch (supports `is_blank`)
- `update_row(table_id, row_id, payload)` — single-row PATCH
- `resolve_field_id(table_id, field_name)` — look up a field ID by name
