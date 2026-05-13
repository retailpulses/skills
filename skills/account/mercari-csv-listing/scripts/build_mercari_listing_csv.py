#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

BASEROW_API = "https://api.baserow.io/api"
IMAGE_URL_RE = re.compile(r"https?://[^,\s]+")
EXCLUDE_MAIN_RE = re.compile(r"^Product Images \(exclude main\)(\d+)$")

UNSUPPORTED_SKU_TYPE_VALUES = {"default", "n/a", "na", "unknown", "-", "ー"}
INVALID_JP_COLOR_HINTS = ("ください", "教えて", "翻訳", "カタカナで", "わかりました")


def load_dotenv(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def resolve_token(cli_token: Optional[str]) -> str:
    if cli_token:
        return cli_token.strip()
    for key in ("BASEROW_TOKEN", "RP_BASEROW_TOKEN", "TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    raise SystemExit("Missing Baserow token. Pass --token or set BASEROW_TOKEN.")


def http_json(req: urllib.request.Request, timeout: int = 120) -> dict:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_table_fields(token: str, table_id: int) -> List[dict]:
    headers = {"Authorization": f"Token {token}"}
    url = f"{BASEROW_API}/database/fields/table/{table_id}/"
    req = urllib.request.Request(url, headers=headers)
    data = http_json(req)
    if isinstance(data, list):
        return data
    return []


def resolve_field_id(token: str, table_id: int, field_name: str) -> int:
    fields = fetch_table_fields(token, table_id)
    for field in fields:
        if str(field.get("name")) == field_name:
            return int(field["id"])
    raise SystemExit(f"Field not found in table {table_id}: {field_name}")


def fetch_rows_by_equal_filter(token: str, table_id: int, field_key: str, values: List[str]) -> List[dict]:
    headers = {"Authorization": f"Token {token}"}
    rows: List[dict] = []
    seen_ids = set()
    for value in sorted(set(v for v in values if v)):
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {
                    "user_field_names": "true",
                    "size": 200,
                    "page": page,
                    f"filter__{field_key}__equal": value,
                }
            )
            url = f"{BASEROW_API}/database/rows/table/{table_id}/?{query}"
            req = urllib.request.Request(url, headers=headers)
            data = None
            for attempt in range(4):
                try:
                    data = http_json(req)
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(1.2 * (attempt + 1))
            batch = (data or {}).get("results", [])
            if not batch:
                break
            for row in batch:
                rid = row.get("id")
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                rows.append(row)
            if len(batch) < 200:
                break
            page += 1
    return rows


def fetch_all_rows(token: str, table_id: int) -> List[dict]:
    headers = {"Authorization": f"Token {token}"}
    rows: List[dict] = []
    page = 1
    while True:
        url = (
            f"{BASEROW_API}/database/rows/table/{table_id}/"
            f"?user_field_names=true&size=200&page={page}"
        )
        req = urllib.request.Request(url, headers=headers)
        data = http_json(req)
        batch = data.get("results", [])
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 200:
            break
        page += 1
    return rows


def parse_item_codes(value: str) -> List[str]:
    if os.path.isfile(value):
        out: List[str] = []
        with open(value, "r", encoding="utf-8") as f:
            for line in f:
                code = line.strip()
                if code:
                    out.append(code)
        return sorted(set(out))
    out = [x.strip() for x in value.split(",") if x.strip()]
    return sorted(set(out))


def parse_urls(cell) -> List[str]:
    if cell is None:
        return []
    if isinstance(cell, str):
        s = cell.strip()
        if not s:
            return []
        hits = IMAGE_URL_RE.findall(s)
        return hits if hits else []
    if isinstance(cell, list):
        urls: List[str] = []
        for it in cell:
            if isinstance(it, dict):
                u = str(it.get("url") or "").strip()
                if u:
                    urls.append(u)
            elif isinstance(it, str):
                u = it.strip()
                if u:
                    urls.append(u)
        return urls
    return []


def get_product_image_urls(row: dict) -> List[str]:
    urls: List[str] = []
    main = row.get("Product Main Image")
    if main:
        u = parse_urls(main)
        if u:
            urls.append(u[0])
    exclude_fields: List[Tuple[int, str]] = []
    for k in row.keys():
        m = EXCLUDE_MAIN_RE.match(k)
        if m:
            exclude_fields.append((int(m.group(1)), k))
    exclude_fields.sort(key=lambda x: x[0])
    for _, k in exclude_fields:
        u = parse_urls(row.get(k))
        if u:
            urls.append(u[0])
    add = parse_urls(row.get("Additional Images"))
    urls.extend(add)
    return [u for u in urls if u]


def num_value(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def str_value(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def choose_shipping_id(shipping_rows: List[dict], fee_value: Optional[float]) -> str:
    if fee_value is None:
        return ""
    best: Optional[Tuple[float, str]] = None
    for row in shipping_rows:
        lo = num_value(row.get("Lower end"))
        hi = num_value(row.get("Upper end"))
        if lo is None or hi is None:
            continue
        sid = str_value(row.get("Shipping ID") or row.get("送料ID") or row.get("shipping_id"))
        if not sid:
            continue
        if lo <= fee_value <= hi:
            return sid
        if fee_value <= hi:
            if best is None or hi < best[0]:
                best = (hi, sid)
    return best[1] if best else ""


def is_usable_main_color_jp(value: str) -> bool:
    if not value:
        return False
    s = value.strip()
    if not s:
        return False
    if s.lower() in UNSUPPORTED_SKU_TYPE_VALUES:
        return False
    if len(s) > 20:
        return False
    if any(x in s for x in ("\n", "。", "、")):
        return False
    if any(hint in s for hint in INVALID_JP_COLOR_HINTS):
        return False
    return True


def sku1_type_from_main_color(main_color_jp_raw) -> str:
    main_color_jp = str_value(main_color_jp_raw)
    if is_usable_main_color_jp(main_color_jp):
        return main_color_jp
    return ""


def best_copy_row(rows: List[dict], item_code: str) -> Optional[dict]:
    item_rows = [r for r in rows if str_value(r.get("Item Code")) == item_code]
    if not item_rows:
        return None
    mercari_rows = []
    for r in item_rows:
        platform = str_value(r.get("Platform") or r.get("Sales Channel") or r.get("platform")).lower()
        if platform in ("mercari", "mercari shops", "mercari shop"):
            mercari_rows.append(r)
    candidates = mercari_rows if mercari_rows else item_rows
    active_rows = [r for r in candidates if bool(r.get("Active"))]
    pick = active_rows if active_rows else candidates
    pick.sort(key=lambda r: int(r.get("id") or 0), reverse=True)
    return pick[0]


def get_copy_text(row: Optional[dict]) -> Tuple[str, str]:
    if not row:
        return "", ""
    title_keys = ["Mercari title", "Title", "商品名", "Mercari タイトル", "mercari_title"]
    desc_keys = [
        "Mercari description",
        "Description",
        "Description 1",
        "Description Text",
        "商品説明",
        "Mercari 説明",
        "mercari_description",
    ]
    title = ""
    desc = ""
    for k in title_keys:
        title = str_value(row.get(k))
        if title:
            break
    for k in desc_keys:
        desc = str_value(row.get(k))
        if desc:
            break
    desc2 = str_value(row.get("Description 2"))
    if desc2:
        desc = (desc + "\n\n" + desc2).strip() if desc else desc2
    return title, desc


def parse_date(v) -> Optional[dt.date]:
    if v is None:
        return None
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        return dt.date.fromisoformat(s[:10])
    except Exception:
        return None


def apply_title_prefix(base_title: str, product_row: dict) -> str:
    title = base_title
    unit_price = num_value(product_row.get("Unit Price"))
    discounted = num_value(product_row.get("Discounted Unit Price"))
    exclusive = num_value(product_row.get("Exclusive Price"))
    target = discounted if discounted is not None else exclusive
    prefixes: List[str] = []
    if unit_price and target and unit_price > 0:
        discount_pct = (unit_price - target) / unit_price * 100
        if discount_pct > 10:
            prefixes.append("数量限定セール")
    rd = parse_date(product_row.get("Restock date"))
    if rd and rd > dt.date.today():
        prefixes.append(rd.strftime("%m/%d") + "再入荷予定")
    if prefixes:
        title = " ".join(prefixes + [title]).strip()
    if len(title) > 130:
        title = title[:130]
    return title


def template_fieldnames(path: str, encoding: str) -> Tuple[List[str], Dict[str, str]]:
    with open(path, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        first = next(reader, None) or {}
    return fields, first


def set_if_exists(row: dict, key: str, value) -> None:
    if key in row:
        row[key] = value


def missing_copy_codes(item_codes: List[str], copy_rows: List[dict]) -> List[str]:
    missing: List[str] = []
    for code in item_codes:
        if not best_copy_row(copy_rows, code):
            missing.append(code)
    return sorted(set(missing))


def run_designated_copywriting_skill(skill_dir: str, missing_codes: List[str], token: str) -> dict:
    if not missing_codes:
        return {"invoked": False, "item_codes": []}
    copy_skill_dir = os.path.normpath(os.path.join(skill_dir, "..", "giga-resource-pack-copywriting"))
    script_path = os.path.join(copy_skill_dir, "scripts", "generate_copywriting_rows.py")
    if not os.path.isfile(script_path):
        raise SystemExit(f"Designated skill runner not found: {script_path}")

    cmd = [
        "python3",
        script_path,
        "--item-codes",
        ",".join(missing_codes),
        "--platform",
        "mercari",
        "--create-only-missing",
    ]
    env = os.environ.copy()
    env["BASEROW_TOKEN"] = token
    proc = subprocess.run(cmd, text=True, capture_output=True, env=env, check=False)
    if proc.returncode != 0:
        raise SystemExit(
            "Failed to run designated skill `giga-resource-pack-copywriting`.\n"
            + (proc.stderr or proc.stdout or "").strip()
        )
    raw = (proc.stdout or "").strip()
    try:
        result = json.loads(raw) if raw else {}
    except Exception:
        result = {"raw_output": raw}
    result["invoked"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Mercari listing CSV with Item Code direct lookup.")
    parser.add_argument("--item-codes", required=True, help="Comma-separated item codes or path to newline file")
    parser.add_argument("--template-csv", required=True, help="Mercari import template CSV path")
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--template-encoding", default="cp932")
    parser.add_argument("--output-encoding", default="utf-8-sig")
    parser.add_argument("--shipping-guide-url", required=True)
    parser.add_argument("--product-info-table-id", type=int, default=912520)
    parser.add_argument("--products-table-id", type=int, default=886994)
    parser.add_argument("--copy-table-id", type=int, default=912536)
    parser.add_argument("--shipping-table-id", type=int, default=914491)
    parser.add_argument("--auto-run-copywriting-skill", action="store_true", default=True)
    parser.add_argument("--no-auto-run-copywriting-skill", dest="auto_run_copywriting_skill", action="store_false")
    parser.add_argument("--fail-on-missing-copy", action="store_true", default=True)
    parser.add_argument("--allow-missing-copy", dest="fail_on_missing_copy", action="store_false")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)
    load_dotenv(os.path.join(skill_dir, ".env"))
    load_dotenv(os.path.join(skill_dir, ".env.local"))

    token = resolve_token(args.token)
    item_codes = parse_item_codes(args.item_codes)
    if not item_codes:
        raise SystemExit("No item codes provided")

    info_field_id = resolve_field_id(token, args.product_info_table_id, "Item Code")
    products_field_id = resolve_field_id(token, args.products_table_id, "item code")
    copy_field_id = resolve_field_id(token, args.copy_table_id, "Item Code")

    info_rows = fetch_rows_by_equal_filter(token, args.product_info_table_id, f"field_{info_field_id}", item_codes)
    products_rows = fetch_rows_by_equal_filter(token, args.products_table_id, f"field_{products_field_id}", item_codes)
    copy_rows = fetch_rows_by_equal_filter(token, args.copy_table_id, f"field_{copy_field_id}", item_codes)
    pre_missing_copy = missing_copy_codes(item_codes, copy_rows)
    copy_skill_run = {"invoked": False, "item_codes": []}
    if pre_missing_copy and args.auto_run_copywriting_skill:
        copy_skill_run = run_designated_copywriting_skill(skill_dir, pre_missing_copy, token)
        copy_rows = fetch_rows_by_equal_filter(token, args.copy_table_id, f"field_{copy_field_id}", item_codes)
    shipping_rows = fetch_all_rows(token, args.shipping_table_id)
    info_map = {str_value(r.get("Item Code")): r for r in info_rows}
    products_map = {str_value(r.get("item code")): r for r in products_rows}

    fieldnames, template_first = template_fieldnames(args.template_csv, args.template_encoding)
    if not fieldnames:
        raise SystemExit("Template CSV has no header")

    out_rows: List[dict] = []
    missing_copy: List[str] = []
    missing_required: List[str] = []
    missing_main_color: List[str] = []

    for code in item_codes:
        info = info_map.get(code)
        prod = products_map.get(code)
        copy_row = best_copy_row(copy_rows, code)
        if not copy_row:
            missing_copy.append(code)

        row = {k: "" for k in fieldnames}
        # keep existing template flag pattern when available
        for k, v in template_first.items():
            if k.startswith("商品画像更新フラグ_") or k.startswith("商品画像登録有無_"):
                row[k] = v

        title, desc = get_copy_text(copy_row)
        if prod:
            title = apply_title_prefix(title, prod)

        set_if_exists(row, "商品名", title)
        set_if_exists(row, "商品説明", desc)
        set_if_exists(row, "SKU1_商品管理コード", code)

        price = str_value((prod or {}).get("Mercari ref pricing"))
        qty = str_value((prod or {}).get("Mercari Qty"))
        set_if_exists(row, "販売価格", price)
        set_if_exists(row, "SKU1_在庫数", qty)
        set_if_exists(row, "SKU1_現在の在庫数", qty)
        sku1_type = sku1_type_from_main_color(
            (prod or {}).get("Main Color (JP)"),
        )
        set_if_exists(row, "SKU1_種類", sku1_type)
        if not sku1_type:
            missing_main_color.append(code)

        category = str_value((prod or {}).get("Mercari category ID") or (info or {}).get("Mercari category ID"))
        set_if_exists(row, "カテゴリID", category)

        fee = num_value((prod or {}).get("Unit Fulfillment Fee (Drop Shipping)"))
        shipping_id = choose_shipping_id(shipping_rows, fee)
        set_if_exists(row, "送料ID", shipping_id)

        set_if_exists(row, "商品の状態", "1")
        set_if_exists(row, "配送方法", "1")
        set_if_exists(row, "発送元の地域", "jp13")
        # Keep new listings unopened for manual review; the upload layer maps
        # `1` to the closed state.
        set_if_exists(row, "商品ステータス", "1")
        set_if_exists(row, "配送料の負担", "2")

        dispatch_days = "1"
        if qty == "5":
            dispatch_days = "5"
        set_if_exists(row, "発送までの日数", dispatch_days)

        images = get_product_image_urls(info or {})
        if len(images) < 20:
            images = images + [args.shipping_guide_url]
        else:
            images = images[:19] + [args.shipping_guide_url]
        images = images[:20]

        for idx, u in enumerate(images, start=1):
            set_if_exists(row, f"商品画像名_{idx}", u)

        # required checks
        required = ["商品名", "商品説明", "販売価格", "カテゴリID", "送料ID"]
        miss = [k for k in required if (k in row and not str_value(row.get(k)))]
        if miss:
            missing_required.append(f"{code}: {','.join(miss)}")

        out_rows.append(row)

    if missing_copy and args.fail_on_missing_copy:
        missing_str = ",".join(sorted(set(missing_copy)))
        if copy_skill_run.get("invoked"):
            raise SystemExit(
                "Missing Mercari copywriting rows after running designated skill "
                "`giga-resource-pack-copywriting`: "
                + missing_str
                + ". Skill output: "
                + json.dumps(copy_skill_run, ensure_ascii=False)
            )
        raise SystemExit(
            "Missing Mercari copywriting rows for Item Code(s): "
            + missing_str
            + ". Please run designated skill `giga-resource-pack-copywriting` first, then rerun this CSV skill."
        )

    out_path = args.output_path or os.path.join(os.getcwd(), f"mercari_listing_{dt.date.today().isoformat()}.csv")
    with open(out_path, "w", encoding=args.output_encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(out_rows)

    print(
        json.dumps(
            {
                "output_path": out_path,
                "item_codes": item_codes,
                "rows_written": len(out_rows),
                "fetched": {
                    "product_info_rows": len(info_rows),
                    "products_rows": len(products_rows),
                    "copy_rows": len(copy_rows),
                },
                "copywriting_skill_run": copy_skill_run,
                "missing_copy": missing_copy,
                "missing_required": missing_required,
                "missing_main_color_for_sku1_type": sorted(set(missing_main_color)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
