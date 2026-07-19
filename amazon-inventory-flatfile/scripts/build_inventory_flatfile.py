#!/usr/bin/env python3
# TODO(2026-07-18): Migrate from Baserow API to Supabase PostgREST.
# This script still uses api.baserow.io — update to SUPABASE_URL/rest/v1/.
# See docs/BASEROW_TO_SUPABASE_MIGRATION.md for the migration plan.
import argparse
import csv
import json
import urllib.request

from openpyxl import load_workbook


def fetch_rows(token, table_id):
    rows = []
    page = 1
    headers = {"Authorization": f"Token {token}"}
    while True:
        url = (
            f"https://api.baserow.io/api/database/rows/table/{table_id}/"
            f"?user_field_names=true&size=200&page={page}"
        )
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        batch = data.get("results", [])
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 200:
            break
        page += 1
    return rows


def max_header_columns(ws):
    last = 0
    for r in range(1, 7):
        for c in range(1, ws.max_column + 1):
            value = ws.cell(r, c).value
            if value not in (None, ""):
                last = max(last, c)
    return last


def normalized_order(row):
    try:
        return float(row.get("order") or row["id"])
    except Exception:
        return float(row["id"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--amazon-table-id", type=int, required=True)
    parser.add_argument("--template-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--sku-field", default="SKU")
    parser.add_argument(
        "--fulfillment-field", default="フルフィルメントチャネルコード (JP)"
    )
    parser.add_argument("--qty-field", default="在庫数 (JP)")
    args = parser.parse_args()

    wb = load_workbook(args.template_path, read_only=True, data_only=False, keep_vba=True)
    ws = wb["テンプレート"]
    col_count = max_header_columns(ws)
    header_rows = []
    for r in range(1, 7):
        header_rows.append(
            [
                ws.cell(r, c).value if ws.cell(r, c).value is not None else ""
                for c in range(1, col_count + 1)
            ]
        )

    amazon_rows = fetch_rows(args.token, args.amazon_table_id)
    amazon_rows.sort(key=normalized_order)

    written = 0
    samples = []
    with open(args.output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerows(header_rows)
        for source in amazon_rows:
            sku = str(source.get(args.sku_field) or "").strip()
            if not sku:
                continue
            row = [""] * col_count
            row[0] = sku
            row[1] = str(source.get(args.fulfillment_field) or "").strip()
            row[2] = str(source.get(args.qty_field) or "").strip()
            writer.writerow(row)
            written += 1
            if len(samples) < 10:
                samples.append(row[:3])

    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "data_rows_written": written,
                "template_columns": col_count,
                "sample_rows": samples,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
