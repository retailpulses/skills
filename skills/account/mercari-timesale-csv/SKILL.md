---
name: mercari-timesale-csv
description: Build Mercari Shops timesale CSV files from scoped Baserow timesale rows, using ShopID, active-window filtering, stock checks, and the Mercari timesale price rules. Use when the user asks to generate a Mercari timesale CSV from a shop/product scope and start/end time.
---

# Mercari Timesale CSV

Use this skill when the task is to generate a Mercari Shops timesale CSV file from a scoped set of products and a requested time window.

## Inputs

- Shop scope
  - one shop or multiple shops
  - `ShopID` is mandatory
  - If the user provides a short shop name, map it to `ShopID` as follows:
    - `Shop1` -> `WMyisFmhbGWyVAPEwsfirn`
    - `Shop2` -> `ZaMyGWzp6hUdgDh5E9ADob`
    - `Shop3` -> `2JGrmZqojnBMfdWrtP2xk3`
    - `Shop4` -> `2JMLHBxjiFHDr55jMwA7fs`

- Product scope
  - all products in the requested shop(s), or
  - an explicit product subset when the user provides it
- Time window
  - start time
  - end time
- Optional mode
  - `CREATE` by default
  - `UPDATE` only when the user explicitly asks for ongoing timesale maintenance

## Outputs

- One Mercari timesale CSV file per shop
- A short run report that lists:
  - included rows
  - excluded rows
  - gap rows
  - output file name
- After CSV generation, backfill `921837` with the generated timesale values for the same scoped rows:
  - `値引き後の表示価格`
  - `値引き開始日時`
  - `値引き終了日時`
  - `Active`

## Write Throughput

- There is no fixed row-write rate guarantee; optimize for the fewest writes, not the most writes.
- Write only the rows that survive all filters and validations.
- Do not rewrite rows whose values did not change.
- Reuse already fetched source rows and schema metadata instead of re-reading them for each row.
- Keep the scope narrow by `ShopID`, product subset, and time window before any write pass.
- Perform backfill only after the final eligible set is confirmed.
- Group the work by shop so one shop can finish without waiting on another.
- Use a small concurrent backfill pool when the target API can accept it safely.
- Treat missing prices, inactive rows, zero stock, and boundary failures as early exits to avoid wasted write attempts.
- Prefer a single final backfill pass over incremental churn on the staging table.
- Verify writes by response payload or targeted row read, not by full-table refresh.
- If the row set is large, process it in the smallest safe chunks and continue from the last confirmed chunk.

### File naming

Use a filename that includes:

- shop identifier or shop label
- listing count
- timesale start time

Example:

- `mercari_timesale_shop4_20260408_1615_2423listings.csv`

## Source Tables

- Stock source table: `408338 / 913031`
- Timesale pricing source table: `393156 / 886994`
- Timesale staging/output table: `410074 / 921837`

## Core Workflow

1. Read the live schema for the staging and source tables.
2. Scope rows by `ShopID`.
3. Scope rows by product selection when the user provides a product subset.
4. Exclude rows that already have an active timesale.
5. Exclude rows with `SKU1_在庫数 <= 0` from `913031`.
6. Resolve the live listing row in `913031` by `Mercari Listing ID`.
7. Resolve `Ref Timesale price` from `886994` using the listing row's item-code link.
8. Calculate `値引き後の表示価格` as:
   - `min(Ref Timesale price, 現在価格 * 0.95)`
   - round down to whole yen before writing
9. Read the stored price boundary fields for the listing when available:
   - `設定可能な値引き後の最低価格`
   - `設定可能な値引き後の最高価格`
10. Exclude the row from the CSV when the computed `値引き後の表示価格` is outside the stored boundary range.
11. Treat missing boundary values as a gap when the boundary check is required for that row.
12. Build one CSV row per eligible product.
13. Preserve the Mercari column order exactly.
14. Write the CSV locally and produce a validation report.

## Selection Rules

- Active timesale means `値引き終了日時` exists and is in the future.
- A row is eligible only when `値引き終了日時` is `null` or stale.
- `ShopID` is required for every source row.
- If a requested row has no usable `Ref Timesale price`, skip it and report the gap.
- If a requested row has no positive stock in `913031`, skip it and report the gap.
- After a Mercari upload result is returned, treat every `成功` row as committed state.
- Do not regenerate committed success rows into a new `CREATE` batch unless the user explicitly wants a fresh re-registration of those same listings.
- If Mercari returns `この商品は既にタイムセール設定中のため新規設定できません`, the row is already active and must be removed from any new `CREATE` batch.

## CSV Rules

- Follow the official Mercari timesale CSV guide.
- Keep the header and column order unchanged.
- Keep unchanged fields in place when the guide requires them.
- Do not invent values for missing source data.
- Do not add a `ShopID` column to the CSV unless the official Mercari format changes.
- Never reuse a previously generated `値引き後の表示価格` from the staging table when the source-of-truth row can be re-read.

## Validation Rules

- `処理フラグ` must be correct for the operation:
  - default to `CREATE`
  - use `UPDATE` only when the user explicitly requests ongoing timesale maintenance

- `CREATE` batches must only contain rows that are not already in an active Mercari timesale state.
- `UPDATE` batches must only contain rows that Mercari already accepts as active timesale rows for maintenance.
- `商品ID` must be present for every row.
- `値引き開始日時` and `値引き終了日時` must be formatted as `yyyy/mm/dd hh:mm`.
- `値引き後の表示価格` must obey the official Mercari limits.
- `値引き後の表示価格` must also fall within the stored Baserow boundary range when those boundary values are present.
- The final file must not include rows that are inactive, out of stock, or missing source price data.

## Reporting Rules

Every run must report:

- total scoped rows
- rows excluded for active timesale
- rows excluded for zero stock
- rows excluded for missing `Ref Timesale price`
- rows excluded because Mercari already reported them as active in a prior upload result
- rows excluded for boundary violations against stored min/max sale price
- rows included in the CSV
- output path
- whether a backfill to `410074 / 921837` was performed
- any rows that required Baserow handling skill use on a need basis

## Definition Of Done

See [references/dod.md](references/dod.md) for the reviewable DoD.

## Versioning

- `v1.0.0` - initial skill definition for Mercari timesale CSV generation.
- `v1.1.0` - added write-throughput guidance and concurrent backfill strategy to reduce wall time.
