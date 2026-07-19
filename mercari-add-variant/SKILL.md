---
name: mercari-add-variant
description: Create or update Mercari listings with multiple product variants (SKUs) grouped under one listing. Reads SPU1-based variant groups from Supabase product_variants and creates multi-variant Mercari products via GraphQL API. Use when adding new color/size variants to a product group, consolidating standalone listings into a multi-variant listing, or creating a new product with all its variants in one listing.
---

# Mercari Add Variant

Creates Mercari listings that group multiple product variants (SKUs sharing the same SPU1) under a single Mercari product, instead of creating one standalone listing per SKU.

## When To Use

- Adding a new product variant (e.g., new color) to an existing product group
- Creating a multi-variant listing from scratch for products sharing the same SPU1
- Consolidating standalone single-SKU listings into one multi-variant product
- Testing multi-variant creation patterns

**Not for:**
- Single-SKU standalone listings (use `mercari-csv-listing`)
- Batch price/stock updates (use `mercari-batch-update`)
- Product group CSV creation for admin panel (use existing product-group CSV tools)

## Data Source

Supabase `baserow_886994_compat_vw` (joins `product_variants` + `product_commercials`) for reading product data. `platform_listings` + `platform_listing_skus` for writing listing IDs. Domain: `product_catalog`, owned by `retailpulses/RPagentOS`.

## How It Works

Mercari products can have up to 10 variants (SKUs) under one listing. Each variant has its own `skuCode`, `stockQuantity`, and optional `name` (e.g., color name). All variants share the same product-level fields: title, description, price, images, category, shipping config.

**Critical API constraint:** Variants can only be set at `createProduct` time. The `updateProduct` mutation does NOT accept a `variants` field. This means:
- ✅ Creating a **new** multi-variant product: supported via `createProduct`
- ❌ Adding a variant to an **existing** product: NOT supported by the API

## Safety Model

```
1. VALIDATE  → Check Supabase: SKU exists, SPU1 group found, target shop confirmed
2. SNAPSHOT  → If modifying existing listings, save full product data before any mutation
3. DRY-RUN   → Preview the CreateProductInput payload, variant list, and affected SKUs
4. CONFIRM   → --execute flag required for live mutations
5. VERIFY    → After creation, query each variant SKU to confirm all resolve to the new product
```

## Modes

| Mode | Description | Removes listings? | Use case |
|------|-------------|:---:|---|
| `create-multi` | Create a new multi-variant product from one or more SPU1 siblings | No | New products, first-time listing |
| `standalone` | Create a single-SKU standalone listing (matches current pipeline default) | No | Quick single-variant addition |

### Mode: `create-multi`

Creates one Mercari product containing all specified variants. Reads pricing, category, images, and description from a template SKU in Supabase (the first variant in the SPU1 group). All variants share the same product-level fields.

```
Supabase SPU1 group (e.g., N504P415032)
├── N504P415032A (Black)  ─┐
├── N504P415032H (Navy)    ├──> One Mercari product with 3+ variants
├── N504P415032N (Ivory)  ─┘
```

**If sibling variants already have standalone listings on the target shop:** Those standalone listings remain untouched. The new multi-variant product is a separate listing. This creates duplicates — use with caution on production shops.

### Mode: `standalone`

Creates a single-SKU product. Functionally identical to the existing `mercari-csv-listing` pipeline's `createProduct` call, but operates on a single SKU directly from Supabase without needing a CSV.

## Quick Start

```bash
# Dry-run: preview what would be created
python tools/add-variant/add_mercari_variant.py \
  --sku N504P415032H \
  --shop shop3 \
  --mode create-multi \
  --dry-run

# Execute: create multi-variant product
python tools/add-variant/add_mercari_variant.py \
  --sku N504P415032H \
  --shop shop3 \
  --mode create-multi \
  --execute

# Standalone single-SKU creation
python tools/add-variant/add_mercari_variant.py \
  --sku N504P415032H \
  --shop shop2 \
  --mode standalone \
  --execute
```

## Instructions

### Phase 1: Supabase Discovery

Query Supabase `baserow_886994_compat_vw` via PostgREST:

1. **Look up the SKU**: Query by `item_code` to get: SPU1, Mercari category ID, pricing, color, qty, product name, image URLs
2. **Find SPU1 siblings**: Query all rows where SPU1 matches the target SKU's SPU1
3. **Check existing listings**: For each sibling, check `platform_listings` for existing `mercari_shop{N}_product_id` on the target shop
4. **Determine mode**:
   - If NO siblings have listings on target shop → `create-multi` (clean start)
   - If some siblings have standalone listings → warn about duplicates, offer `create-multi` or `standalone`
   - If the SKU itself already has a listing → report and skip

### Phase 2: Build & Validate Payload

1. **Template from Supabase**: Use the first available SPU1 sibling's data for: product name, category ID, description, image URLs, pricing
2. **Build variants array**: One entry per SKU with `{skuCode, stockQuantity, name}` where `name` = `representative_color_ja` from Supabase (or `main_color` if JP unavailable)
3. **Set product fields**: Price from `mercari_effective_price_excl_shipping` or `mercari_stable_price_excl_shipping`, shipping defaults to SELLER (送料込み), status defaults to UNOPENED for safety
4. **Validate**: Category ID non-empty, at least one variant, price > 0, image URLs accessible

### Phase 3: Execute (via mercari-shop-api-specialist)

Delegate API execution to `mercari-shop-api-specialist`:
- Token resolution for target shop
- `createProduct` mutation via SSH to ConoHa VPS (`root@160.251.141.110`)
- Handle GraphQL errors with diagnostic field removal if needed

### Phase 4: Verify & Record

1. Query each variant SKU via `productVariant(by: {skuCode})` — confirm all resolve to the same product ID
2. Save result JSON to `tools/add-variant/results/` with product ID, variant IDs, timestamp
3. Optionally update Supabase `platform_listings`: set `mercari_shop{N}_product_id` for the SKUs that were listed

## CLI Reference

```
add_mercari_variant.py
  --sku SKU               Target SKU (item_code from Supabase)
  --shop {shop1,shop2,shop3,shop4}
                          Target Mercari shop
  --mode {create-multi,standalone}
                          create-multi: all SPU1 siblings as variants (default)
                          standalone: single-SKU listing only
  --variants SKU,SKU,...  Optional: explicit variant SKU list (overrides SPU1 auto-discovery)
  --status {UNOPENED,OPENED}
                          Listing status (default: UNOPENED for safety)
  --price PRICE           Override price (default: from Supabase)
  --dry-run               Preview payload without executing
  --execute               Execute the createProduct mutation
  --result-dir DIR        Output directory for result JSON (default: ./results/)
```

## GraphQL Operations

### createProduct (multi-variant)

```graphql
mutation createProduct($input: CreateProductInput!) {
  createProduct(input: $input) {
    product {
      id
      name
      status
      variants {
        id
        skuCode
        stockQuantity
        name
      }
    }
  }
}
```

### productVariant (verification)

```graphql
query productVariant($by: ProductVariantBy!) {
  productVariant(by: $by) {
    id
    skuCode
    stockQuantity
    product { id name status }
  }
}
```

## Integration

| Skill | Role |
|-------|------|
| `mercari-shop-api-specialist` | VPS SSH execution, token resolution, GraphQL error handling |

This skill is the **decision layer**: it reads Supabase to determine which mode to use, builds the payload, and delegates API execution to the specialist skill.

## Credentials

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — service_role key for reads/writes
- `MERCARI_SHOP{N}_TOKEN` — Mercari shop API tokens

## Rollback

For `create-multi` mode (new listing): No rollback needed — the original standalone listings are untouched. Set the new product to `DRAFT` status via `updateProduct` if it was created in error.

For scenarios involving existing product modification (future): See `references/rollback.md`.

## Limitations

- Mercari API cannot add variants to an existing product — only at `createProduct` time
- Max 10 variants per product (Mercari limit)
- Product name max 120 chars, description max 2000 chars, images max 20
- Duplicate SKU codes across different products will cause API errors
- Image URLs must be publicly accessible (CDN URLs work; local files don't)
