---
name: sync-giga-saved-products
description: Sync GigaB2B saved products into Baserow table 886994 from explicit Item Codes or from the last 30 days of newly saved products, using the documented Baserow and GigaB2B API access flow, skipping existing Item Codes and creating new records only.
---

# Sync Giga Saved Products

Use this skill when the user wants to sync GigaB2B saved products into Baserow `886994`.

## Input Modes

Support two modes:

1. Explicit `Item Code` list.
2. Default mode: newly added saved products from the last 30 days.

If the user does not clearly specify a mode, ask which mode to use.

## Workflow

1. Read the user input and normalize the requested mode.
2. Load the live Baserow schema for table `886994` before writing anything.
3. Use the documented GigaB2B saved-products API flow to fetch the requested saved-product set.
4. Deduplicate the source set by `Item Code`.
5. Query Baserow `886994` and build the existing `Item Code` set.
6. Skip any source row whose `Item Code` already exists.
7. Create new Baserow rows only for new `Item Code` values.
8. Leave unrelated fields unchanged or blank unless the source data provides a safe value.
9. Verify the write result by re-reading the created rows.

## Write Rules

- `Item Code` is the unique key.
- Never create a duplicate row for an existing `Item Code`.
- Never update existing rows unless the user explicitly asks for an update workflow.
- Do not invent source values that are not present in GigaB2B or Baserow.
- Keep the operation append-only.

## Default Behavior

- If the user gives explicit item codes, sync only those codes.
- If the user gives no item codes and no other mode hint, use the last-30-days saved-products sync.
- If the saved-products retrieval path is unclear from the repo context, stop and confirm before guessing.

## Baserow Access

- Read Baserow rows with the live API and `user_field_names=true`.
- Target table for this skill: `886994`.
- Treat `Item Code` as the unique lookup key.
- For reads, fetch existing rows first and build a set of existing `Item Code` values.
- For writes, POST only the new rows that do not already exist.
- Keep the workflow append-only unless the user explicitly asks for updates.
- Do not invent values for fields that are not present in the source row.

## GigaB2B Access

- Saved-product data is fetched from `https://openapi.gigab2b.com`.
- Saved-products endpoint:
  - `POST /b2b-overseas-api/v1/buyer/product/skus/v1`
- Required headers:
  - `client-id`
  - `timestamp`
  - `nonce`
  - `sign`
  - `Content-Type: application/json`
- Signature construction:
  - `message = clientId & apiPath & timestamp & nonce`
  - `key = clientId & clientSecret & nonce`
  - `sign = base64(HMAC-SHA256(message, key).hex())`
- Request body for the last-30-days sync:
  - `queryTimeType = 2`
  - `startTime`
  - `endTime`
  - `page`
  - `pageSize = 100`
  - `sort = 4`
- Response fields used by this skill:
  - `data.records[].sku`
  - `data.records[].productName`
  - `data.records[].updateTime`
  - `data.records[].firstArrivalDate`
  - `data.records[].addedTime`
- The last-30-days mode should be interpreted as collection/saved time, not product creation time.

## Reference

- See [GIGAB2B_API_ACCESS.md](references/GIGAB2B_API_ACCESS.md) for the repo-specific auth and API access flow.

## Note: This Skill is Deprecated

This skill has been merged into **`gigab2b-workflow`** which now includes:

- **Query Mode** — direct GigaB2B API queries (product detail, price, shipping, saved-products).
- **Sync Mode** — the append-only sync described in this file.
- **Patch Incomplete Mode** — scan Baserow table 886994 for rows with blank mandatory fields (`Product Name`, `Product Features`, `Product Specification`, `Store Code`, `Store Name`, `Product Main Image`, `Image URLs JSON`, `Unit Price`, `Unit Fulfillment Fee (Drop Shipping)`) and fill them using GigaB2B detail and price API data, without overwriting existing content.

Use `gigab2b-workflow` for all GigaB2B ↔ Baserow operations going forward.
