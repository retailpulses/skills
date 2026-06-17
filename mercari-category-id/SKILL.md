---
name: mercari-category-id
description: Populate Mercari category IDs in Baserow Products by reading the live schema, matching category master data against Product Name, and writing the Mercari category ID field with exact-match-first and parent-category fallback rules.
---

# Mercari Category ID

Use this skill when the user wants to write Mercari category IDs into Baserow `Products` or into a local CSV from a category master CSV or similar live master data.

This skill is for live Baserow work, not browser automation.

## Workflow

1. Detect the input mode.
2. If the user gave Baserow `Products`, confirm the live schema before writing anything.
3. If the user gave a CSV, inspect the header first and preserve all other columns.
4. Load the category master CSV and build a lookup from category name and full path.
5. Match primarily from `Product Name` or the product-name column in the CSV.
6. Write `Mercari category ID` only.
7. Run a 100-row pilot first when the task is new or the match quality is uncertain.
8. If the pilot looks correct, continue with the remaining rows and verify after write.

## Live Schema Rules

- Always inspect the live table schema before assuming any field name.
- Use `Authorization: Token <database_token>` for row reads and writes.
- Use `user_field_names=true` so field keys are readable.
- Page through full tables with `size=200&page=<n>` when reading more than one page.
- Treat `Mercari category ID` as the writable target field if the live schema confirms that exact label.
- Do not write any other field unless the user explicitly asks.
- If the task is on live Baserow `Products`, keep the workflow row-level and append-free; do not change the schema.
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
- Use batch writes when possible.
- Re-read after write to confirm there are no remaining blank `Mercari category ID` cells.

## Operational Guardrails

- Refresh live Baserow data before any production write.
- Do not rely on older local snapshots.
- Do not use browser automation when the API path is available.
- Do not change unrelated fields.
- Do not invent category IDs when the title does not support a safe decision.
- If the live schema or master data does not match expectations, stop and ask for clarification.

## When Not To Use This Skill

- Do not use it for Rakuten, Amazon, or Mercari copywriting.
- Do not use it for inventory, price, or stock updates.
- Do not use it if the task is about categories outside Baserow `Products`.
