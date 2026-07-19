---
name: mercari-category-id
description: Populate Mercari category IDs in Supabase product_variants by reading the live schema, matching category master data against Product Name, and writing the Mercari category ID field with exact-match-first and parent-category fallback rules.
---

# Mercari Category ID

Use this skill when the user wants to write Mercari category IDs into Supabase `product_variants` (via `baserow_886994_compat_vw`) or into a local CSV from a category master CSV or similar live master data.

This skill is for live Supabase work via PostgREST API, not browser automation.

## Data Source

Supabase `baserow_886994_compat_vw` — a compatibility view joining `product_variants` + `product_commercials`. Owned by `retailpulses/RPagentOS` (domain: `product_catalog`).

## Workflow

1. Detect the input mode.
2. If the user gave Supabase data, confirm the live schema via PostgREST before writing anything.
3. If the user gave a CSV, inspect the header first and preserve all other columns.
4. Load the category master CSV and build a lookup from category name and full path.
5. Match primarily from `Product Name` or the product-name column in the CSV.
6. Write `Mercari category ID` only to `product_variants.mercari_category_id`.
7. Run a 100-row pilot first when the task is new or the match quality is uncertain.
8. If the pilot looks correct, continue with the remaining rows and verify after write.

## Live Schema Rules

- Always inspect the live table schema before assuming any field name.
- Use PostgREST API (`SUPABASE_URL/rest/v1/`) with `Authorization: Bearer <service_role_key>`.
- Use `Accept: application/json` and `Prefer: return=representation` headers.
- Page through results with Range headers when reading more than one page.
- Treat `mercari_category_id` as the writable target field in `product_variants`.
- Do not write any other field unless the user explicitly asks.
- Keep the workflow row-level and append-free; do not change the schema.
- If the task is on a CSV file, preserve all other columns and only add or update the category column.

## CSV Input Rules

- If the input is a CSV file, read the header first and identify the product-name column.
- If the CSV already has a `CategoryID` column, fill it.
- If the CSV does not have a `CategoryID` column, create it in the output.
- Preserve all other columns and row order.
- If the CSV has no clear product-name column, ask for clarification before writing.
- For CSV mode, the output should be a CSV file with the category column added or updated.

## Matching Rules

- Use `Product Name` as the primary signal.
- Prefer exact title matches first.
- If no exact match exists, fall back to the nearest parent category that is still safe.
- If a product title is too short or ambiguous, use sibling-family context when available.
- If no safe category exists, leave the row untouched and report it.

- Normalize category names before matching:
  - split category names on `・`, `/`, and `／`
  - ignore noisy tokens such as `セット` when they are only modifiers
  - prefer longer and deeper category paths over short generic terms
- Do not use color, quantity, or packaging words as the main category signal.
- Keep the classification conservative. Parent fallback is better than a risky forced leaf.

## Write Strategy

- First do a 100-row pilot write.
- Read the pilot rows back and verify the results.
- If the pilot is acceptable, continue in batches.
- Use PostgREST PATCH with `in` filter for batch updates.
- Re-read after write to confirm there are no remaining blank `mercari_category_id` cells.

## Credentials

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — service_role key for writes
- `BASEROW_TOKEN` (legacy) — no longer used; ignore if present

## Operational Guardrails

- Refresh live Supabase data before any production write.
- Do not rely on older local snapshots.
- Do not use browser automation when the API path is available.
- Do not change unrelated fields.
- Do not invent category IDs when the title does not support a safe decision.
- If the live schema or master data does not match expectations, stop and ask for clarification.

## When Not To Use This Skill

- Do not use it for Rakuten, Amazon, or Mercari copywriting.
- Do not use it for inventory, price, or stock updates.
- Do not use it if the task is about categories outside Supabase product_variants.
