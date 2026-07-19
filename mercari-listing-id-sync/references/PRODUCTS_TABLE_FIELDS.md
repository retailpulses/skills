# Supabase platform_listings — Mercari Listing ID Fields

## Schema

- **Database**: retailpulses_shared (Supabase)
- **Table**: `platform_listings`
- **Domain**: `product_catalog` (owned by `retailpulses/RPagentOS`)
- **Join key**: `item_code` in `product_variants` ↔ `skuCode` in Mercari GraphQL `productVariant`

## Mercari ShopX Product ID Fields

These fields in `platform_listings` hold the Mercari `product.id` for each shop's listing.

| Shop Key | Column Name | Mercari Shop ID |
|----------|------------|-----------------|
| `shop1` | `mercari_shop1_product_id` | `WMyisFmhbGWyVAPEwsfirn` |
| `shop2` | `mercari_shop2_product_id` | `ZaMyGWzp6hUdgDh5E9ADob` |
| `shop3` | `mercari_shop3_product_id` | `2JGrmZqojnBMfdWrtP2xk3` |
| `shop4` | `mercari_shop4_product_id` | `2JMLHBxjiFHDr55jMwA7fs` |

## Writing to These Fields

### Single Row Update (PostgREST)

```
PATCH /rest/v1/platform_listings?item_code=eq.SKU001
Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>
Content-Type: application/json
Prefer: return=representation

{"mercari_shop1_product_id": "m1234567890"}
```

### Batch Update via RPagentOS Internal API

For bulk updates, prefer the RPagentOS internal API or use PostgREST with multiple PATCH requests. Respect rate limits and batch to 100 rows max per request.

## Idempotency

- **Write only to rows where the target field is NULL.** If a row already has a `mercari_shopX_product_id`, skip it (unless `--overwrite` is explicitly passed).
- This makes repeated runs safe — only newly discovered listings get written.

## Candidate Query (Discovery Mode)

For efficient candidate fetching, use PostgREST with null filter:

```
GET /rest/v1/baserow_886994_compat_vw?select=item_code&mercari_shop1_product_id=is.null&item_code=not.is.null&limit=200
```

This returns only rows where the shop's field is empty and `item_code` is set.

## Supabase Access

Use PostgREST API via `SUPABASE_URL/rest/v1/` with `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>`. For Python, use `supabase-py` or `httpx` directly against the REST API.
