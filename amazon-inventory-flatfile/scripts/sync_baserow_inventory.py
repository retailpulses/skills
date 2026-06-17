#!/usr/bin/env python3
import argparse
import json
import urllib.request


def normalize_qty(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


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


def patch_rows(token, table_id, items):
    if not items:
        return []
    url = (
        f"https://api.baserow.io/api/database/rows/table/{table_id}/batch/"
        f"?user_field_names=true"
    )
    body = json.dumps({"items": items}).encode()
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode()).get("items", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--products-table-id", type=int, required=True)
    parser.add_argument("--amazon-table-id", type=int, required=True)
    parser.add_argument("--products-item-code-field", default="item code")
    parser.add_argument("--products-qty-field", default="Qty Available")
    parser.add_argument("--amazon-item-code-field", default="Item Code")
    parser.add_argument("--amazon-qty-field", default="在庫数 (JP)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    products = fetch_rows(args.token, args.products_table_id)
    amazon_rows = fetch_rows(args.token, args.amazon_table_id)

    product_map = {}
    for row in products:
        item_code = str(row.get(args.products_item_code_field) or "").strip()
        if item_code:
            product_map[item_code] = normalize_qty(row.get(args.products_qty_field))

    updates = []
    matched_rows = 0
    unmatched_rows = 0
    blank_item_code_rows = 0
    unchanged_rows = 0

    for row in amazon_rows:
        item_code = str(row.get(args.amazon_item_code_field) or "").strip()
        current_qty = normalize_qty(row.get(args.amazon_qty_field))
        if not item_code:
            blank_item_code_rows += 1
            target_qty = "0"
        elif item_code not in product_map:
            unmatched_rows += 1
            target_qty = "0"
        else:
            matched_rows += 1
            target_qty = product_map[item_code]

        if current_qty == target_qty:
            unchanged_rows += 1
            continue

        updates.append({"id": row["id"], args.amazon_qty_field: target_qty})

    updated_rows = 0
    if not args.dry_run:
        for start in range(0, len(updates), 100):
            batch = updates[start : start + 100]
            updated_rows += len(patch_rows(args.token, args.amazon_table_id, batch))

    print(
        json.dumps(
            {
                "products_rows": len(products),
                "amazon_rows": len(amazon_rows),
                "matched_rows": matched_rows,
                "unmatched_rows": unmatched_rows,
                "blank_item_code_rows": blank_item_code_rows,
                "unchanged_rows": unchanged_rows,
                "update_candidates": len(updates),
                "updated_rows": 0 if args.dry_run else updated_rows,
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
