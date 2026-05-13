# Mercari Timesale CSV Skill - Definition of Done

## Scope

- User provides:
  - shop scope
  - product scope
  - start time
  - end time
- `ShopID` is mandatory for every run.
- Output is a Mercari-compliant CSV file, one file per shop.

## Done When

1. The live Baserow schema has been read for the source tables.
2. Rows are filtered by `ShopID`.
3. Rows with active timesale windows are excluded.
4. Rows with `SKU1_在庫数 <= 0` in `913031` are excluded.
5. The live listing row is resolved in `913031` by `Mercari Listing ID`.
6. `Ref Timesale price` is resolved from `886994` using the listing row's item-code link.
7. `値引き後の表示価格` is calculated from:
   - `min(Ref Timesale price, 現在価格 * 0.95)`
   - rounded down to a whole yen
8. If the listing row has stored boundary values, the computed `値引き後の表示価格` is checked against:
   - `設定可能な値引き後の最低価格`
   - `設定可能な値引き後の最高価格`
9. Rows outside the boundary range are excluded from the CSV.
10. The generated CSV follows the Mercari official column order.
11. The CSV file name includes:
   - shop identifier or shop label
   - number of listings
   - start time
12. If a Mercari import result has already returned `成功` for any rows, those rows are treated as committed and are not regenerated into a new `CREATE` batch.
13. If Mercari returns `この商品は既にタイムセール設定中のため新規設定できません`, those rows are excluded from the next `CREATE` candidate set.
14. `CREATE` is the default processing mode.
    - `UPDATE` is only used when the user is maintaining an already-active timesale set.
15. `410074 / 921837` is backfilled with:
   - generated `値引き後の表示価格`
   - `値引き開始日時`
   - `値引き終了日時`
   - `Active`
16. A run report is written with:
   - included rows
   - excluded rows
   - missing-price gaps
   - zero-stock gaps
   - rows excluded because Mercari already reported them as active in a prior upload result
   - rows excluded for boundary violations against stored min/max sale price
   - output path
   - whether Baserow handling skill was needed on a case-by-case basis
17. The CSV is validated before delivery.

## Not Done When

- any requested shop is missing from the output
- active timesale rows are included by mistake
- zero-stock rows are included
- a row is fabricated without source data
- committed success rows are regenerated into a new CREATE batch without an explicit user request
- a stale staging-table timesale price is reused instead of recomputing from source-of-truth rows
- a computed timesale price falls outside stored min/max boundary values and is still included
- the output CSV does not match the Mercari timesale layout
- the staging table backfill is not completed when required
