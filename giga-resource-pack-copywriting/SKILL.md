---
name: giga-resource-pack-copywriting
description: Generate Japanese Rakuten, Amazon, and Mercari copy from a Giga Item Code by looking up the resource pack in Supabase resource_packs, applying platform strategy records from platform_copy_strategies, and writing outputs to copywriting_outputs. Also supports explicit ZIP-input fallback when the user provides a local pack.
---

# Giga Resource Pack Copywriting

Use this skill when the user wants `Item Code -> resource pack lookup -> marketplace copywriting`.

Supported outputs:

- `Rakuten`
- `Amazon`
- `Mercari`

## Data Source

Supabase tables (domain: `product_catalog`, owned by `retailpulses/RPagentOS`):

| Table | Purpose | Replaces |
|-------|---------|----------|
| `resource_packs` | Item-Code-indexed product pack data | Baserow 912520 |
| `platform_copy_strategies` | Platform-specific copywriting rules | Baserow 912423 |
| `copywriting_outputs` | Generated copy text per item/platform | Baserow 912536 |

Primary mode:

- input is `Item Code`
- look up source pack-derived product info in Supabase `resource_packs`
- apply platform copy strategy records from Supabase `platform_copy_strategies`
- write final copy to Supabase `copywriting_outputs`
- facts first, copy second
- parent-level copy by default
- no market research unless the user explicitly asks

Fallback mode:

- if the user explicitly provides a local ZIP instead of an Item Code, use the ZIP directly
- still prefer writing final outputs to Supabase if the task asks for it

## Supabase Access

Use PostgREST API:

- `GET /rest/v1/resource_packs?item_code=eq.SKU001`
- `GET /rest/v1/platform_copy_strategies?platform=eq.rakuten&is_active=is.true`
- `POST /rest/v1/copywriting_outputs` with `Prefer: return=representation`

Authenticate with `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>`.

## Credentials

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — service_role key for reads/writes
- `GIGA_CLIENT_ID` and `GIGA_CLIENT_SECRET` — for resource pack retrieval
- `BASEROW_TOKEN` (legacy) — no longer used

## Scripts

- `scripts/generate_copywriting_rows.py` — canonical copywriting pipeline
