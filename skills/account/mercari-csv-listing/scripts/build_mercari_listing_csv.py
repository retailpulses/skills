#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests

BASEROW_API = "https://api.baserow.io/api"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mercari_text_utils

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


def _baserow_headers(token: str) -> dict:
    return {"Authorization": f"Token {token}"}


def _get_with_retry(session: requests.Session, url: str, token: str, timeout: int = 120) -> dict:
    last_exc = None
    for attempt in range(4):
        try:
            resp = session.get(url, headers=_baserow_headers(token), timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == 3:
                raise
            time.sleep(1.2 * (attempt + 1))
    raise last_exc


def fetch_rows_by_equal_filter(session: requests.Session, token: str, table_id: int, field_key: str, values: List[str]) -> List[dict]:
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
            data = _get_with_retry(session, url, token)
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


def parse_item_codes(value: str) -> List[str]:
    if os.path.isfile(value):
        out: List[str] = []
        with open(value, "r", encoding="utf-8") as f:
            first = f.readline().strip()
            if "," in first or "code" in first.lower() or "name" in first.lower():
                for line in f:
                    code = line.strip().split(",")[0].strip('"').strip()
                    if code:
                        out.append(code)
            else:
                if first:
                    out.append(first)
                for line in f:
                    code = line.strip()
                    if code:
                        out.append(code)
        return sorted(set(out))
    out = [x.strip() for x in value.split(",") if x.strip()]
    return sorted(set(out))


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


def is_usable_main_color(value: str) -> bool:
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
    # Strip SKU prefix first so it's gone before any title prefixes are added
    base_title = re.sub(r"^[A-Z0-9-]+\s*", "", base_title)
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
        title = re.sub(r"\s+", " ", title)[:130]
    return title


def build_description(prod: dict, prefix: str, footer: str) -> str:
    spec = str_value(prod.get("Product Specification"))
    if not spec:
        return ""
    parts = [prefix, "", "【商品説明】", "", spec]
    if footer:
        parts.extend(["", footer])
    return "\n".join(parts).strip()


def parse_urls(cell) -> List[str]:
    if cell is None:
        return []
    if isinstance(cell, str):
        s = cell.strip()
        if not s:
            return []
        hits = re.findall(r"https?://[^,\s]+", s)
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


def head_filter_image_urls(urls: List[str]) -> Tuple[List[str], int, int]:
    valid: List[str] = []
    excluded = 0
    failed = 0
    for u in urls:
        try:
            req = urllib.request.Request(u, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                cl = resp.headers.get("Content-Length")
                if cl and int(cl) >= 10_485_760:
                    excluded += 1
                    continue
            valid.append(u)
        except Exception:
            failed += 1
            valid.append(u)
    return valid, excluded, failed


def fetch_giga_images(item_codes: List[str]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    if not item_codes:
        return result
    try:
        resp = mercari_text_utils._giga_post(
            "/b2b-overseas-api/v1/buyer/product/detailInfo/v1",
            {"skus": list(set(item_codes))},
            timeout=120,
        )
    except Exception:
        return result
    data_list = resp.get("data") if isinstance(resp, dict) else resp
    if not isinstance(data_list, list):
        return result
    for detail in data_list:
        sku = detail.get("sku")
        image_urls = detail.get("imageUrls") or []
        if sku and isinstance(image_urls, list):
            urls = [u for u in image_urls if isinstance(u, str) and u.startswith("http")]
            if urls:
                result[sku] = urls
    return result


def get_product_images(prod: dict, giga_images: List[str], shipping_guide_url: str, do_head_filter: bool = False) -> List[str]:
    urls: List[str] = []
    img_json = parse_urls(prod.get("Image URLs JSON"))
    if img_json:
        urls.extend(img_json)
    else:
        main_img = parse_urls(prod.get("Product Main Image"))
        if main_img:
            urls.append(main_img[0])
        for u in giga_images:
            if u not in urls:
                urls.append(u)
    if do_head_filter:
        valid, _excluded, _failed = head_filter_image_urls(urls)
        urls = valid if valid else urls
    if len(urls) < 20:
        urls = urls + [shipping_guide_url]
    else:
        urls = urls[:19] + [shipping_guide_url]
    return urls[:20]


def template_fieldnames(path: str, encoding: str) -> Tuple[List[str], Dict[str, str]]:
    with open(path, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        first = next(reader, None) or {}
    return fields, first


def set_if_exists(row: dict, key: str, value) -> None:
    if key in row:
        row[key] = value


DEFAULT_DESC_PREFIX = (
    "ホムブリスショップへようこそ\n"
    "♪すべての商品は未開封の新品です\n"
    "♪フォロー割あり\n"
    "♪まとめ買い割あり：2点で2%OFF、3点で3%OFF、最大5%（一部商品適用外）\n"
    "♪発送と送料：在庫品は1～2営業日以内に発送、再入荷商品は入荷後1～2営業日以内に発送いたします。"
    "北海道は基本的に追加送料不要です。沖縄への送料は別途お見積りが必須です。"
)


CORE_NOUNS = {"家具", "ベッド", "チェア", "テーブル", "収納", "ラック", "ソファ", "デスク", "キャビネット", "マットレス", "スツール", "棚", "机"}
DIM_KEYWORDS = {"cm", "mm", "幅", "奥行", "高さ", "サイズ", "寸法"}


def compute_score(
    title: str,
    desc: str,
    image_count: int,
    has_category: bool,
    price_val: Optional[float],
    has_sku_type: bool,
    qty_val: Optional[float],
    inv_status: str,
    has_shipping_guide: bool,
    unit_price: Optional[float],
    discounted_price: Optional[float],
    spec_text: str,
    n_valid_images: int,
) -> dict:
    gates: List[str] = []
    modules: Dict[str, int] = {}

    if not title:
        gates.append("BLOCKED:no_title")
    if len(title) > 130:
        gates.append("BLOCKED:title_too_long")
    if not desc:
        gates.append("BLOCKED:no_description")
    if len(desc) > 3000:
        gates.append("BLOCKED:description_too_long")
    if n_valid_images == 0:
        gates.append("BLOCKED:no_images")
    if not price_val or price_val == 0:
        gates.append("BLOCKED:no_price")

    title_len = len(title) if title else 0
    if not title or title_len == 0:
        modules["title"] = 0
    elif title_len < 80:
        modules["title"] = 2
    elif title_len <= 99:
        modules["title"] = 8
    elif title_len <= 130:
        modules["title"] = 14
    else:
        modules["title"] = 0

    if title and any(noun in title for noun in CORE_NOUNS):
        modules["title"] = min(modules["title"], 14)
        if any(dk in title for dk in DIM_KEYWORDS):
            modules["title"] = min(modules["title"] + 2, 14)
    elif title:
        modules["title"] = min(modules["title"], 4)

    desc_len = len(desc) if desc else 0
    if not desc or desc_len == 0:
        modules["description"] = 0
    elif desc_len < 500:
        modules["description"] = 2
    elif desc_len <= 1199:
        modules["description"] = 6
    elif desc_len <= 1999:
        modules["description"] = 10
    elif desc_len <= 3000:
        modules["description"] = 14
    else:
        modules["description"] = 0

    bullet_count = desc.count("・") if desc else 0
    if bullet_count >= 3:
        modules["description"] = min(modules["description"] + 2, 14)

    if n_valid_images == 0:
        modules["images"] = 0
    elif n_valid_images <= 2:
        modules["images"] = 4
    elif n_valid_images <= 6:
        modules["images"] = 8
    elif n_valid_images <= 9:
        modules["images"] = 11
    elif n_valid_images <= 14:
        modules["images"] = 13
    else:
        modules["images"] = 14

    modules["category"] = 12 if has_category else 0

    if not price_val or price_val == 0:
        modules["pricing"] = 0
    elif price_val < 1000:
        modules["pricing"] = 4
    elif price_val < 5000:
        modules["pricing"] = 8
    else:
        modules["pricing"] = 12

    modules["variant"] = 8 if has_sku_type else 0

    if not qty_val or qty_val == 0:
        modules["inventory"] = 0
    elif inv_status in ("Incoming Stock", "Restocked"):
        modules["inventory"] = 6
    else:
        modules["inventory"] = 8

    modules["shipping_guide"] = 6 if has_shipping_guide else 0

    if discounted_price is not None and unit_price is not None and unit_price > 0:
        discount_pct = (unit_price - discounted_price) / unit_price * 100
        if discount_pct > 10:
            modules["discount"] = 6
        elif discount_pct > 0:
            modules["discount"] = 4
        else:
            modules["discount"] = 2
    else:
        modules["discount"] = 2

    spec_len = len(spec_text) if spec_text else 0
    if not spec_text:
        modules["spec_length"] = 0
    elif spec_len < 200:
        modules["spec_length"] = 2
    elif spec_len <= 799:
        modules["spec_length"] = 4
    else:
        modules["spec_length"] = 6

    total = sum(modules.values())
    blocked = len(gates) > 0

    return {
        "total": total,
        "modules": modules,
        "gates": gates,
        "blocked": blocked,
        "auto_open": not blocked and total >= 80,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Mercari listing CSV from Item Codes (seller-paid shipping, single table 886994).")
    parser.add_argument("--item-codes", required=True, help="Comma-separated item codes or path to newline file")
    parser.add_argument("--template-csv", required=True, help="Mercari import template CSV path")
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--template-encoding", default="utf-8-sig")
    parser.add_argument("--output-encoding", default="utf-8-sig")
    parser.add_argument("--shipping-guide-url", required=True, help="URL of shipping fee guide image to append")
    parser.add_argument("--products-table-id", type=int, default=886994)
    parser.add_argument("--description-prefix", default=DEFAULT_DESC_PREFIX)
    parser.add_argument("--description-footer", default="")
    parser.add_argument("--score", action="store_true", help="Enable 10-module quality scoring")
    parser.add_argument("--auto-open-qualified", action="store_true", help="Set 商品ステータス=2 for score >= 80 (requires --score)")
    parser.add_argument("--baserow-workers", type=int, default=10, help="Number of parallel Baserow read workers (default: 10)")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(script_dir, ".env"))
    load_dotenv(os.path.join(script_dir, ".env.local"))
    load_dotenv(os.path.join(os.path.dirname(script_dir), ".env"))
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(script_dir))), ".env"))
    # Also check CWD for .env (project root search)
    load_dotenv(os.path.join(os.getcwd(), ".env"))
    load_dotenv(os.path.join(os.getcwd(), ".env.local"))

    token = resolve_token(args.token)
    item_codes = parse_item_codes(args.item_codes)
    if not item_codes:
        raise SystemExit("No item codes provided")

    fieldnames, template_first = template_fieldnames(args.template_csv, args.template_encoding)
    if not fieldnames:
        raise SystemExit("Template CSV has no header")

    session = requests.Session()

    sys.stderr.write(f"Fetching {len(item_codes)} codes from table {args.products_table_id} with {args.baserow_workers} workers...\n")

    products: List[dict] = []
    batches = [[c] for c in item_codes]

    with ThreadPoolExecutor(max_workers=args.baserow_workers) as executor:

        def fetch_one(code: str) -> List[dict]:
            return fetch_rows_by_equal_filter(session, token, args.products_table_id, "field_7670234", [code])

        fut_map = {executor.submit(fetch_one, b[0]): i for i, b in enumerate(batches)}
        for f in as_completed(fut_map):
            try:
                products.extend(f.result())
            except Exception as exc:
                sys.stderr.write(f"  Batch {fut_map[f]} failed: {exc}\n")

    products_map = {str_value(r.get("item code")): r for r in products}
    found_codes = set(products_map.keys())
    missing_codes = sorted(set(item_codes) - found_codes)

    if missing_codes:
        missing_path = os.path.join(
            os.path.dirname(args.output_path or "."),
            f"missing_products_{dt.date.today().isoformat()}.csv",
        )
        with open(missing_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["item code"])
            for c in missing_codes:
                writer.writerow([c])

    present_codes = [c for c in item_codes if c in found_codes]
    sys.stderr.write(f"Found {len(present_codes)} codes in 886994, {len(missing_codes)} missing\n")

    # Overlap GigaB2B image fetch with main processing
    giga_future = None
    if present_codes:
        giga_batches = [present_codes[i:i + 50] for i in range(0, len(present_codes), 50)]

        def fetch_all_giga():
            result: Dict[str, List[str]] = {}
            for chunk in giga_batches:
                try:
                    result.update(fetch_giga_images(chunk))
                except Exception:
                    pass
            return result

        giga_future = ThreadPoolExecutor(max_workers=1).submit(fetch_all_giga)

    sys.stderr.write(f"Building {len(present_codes)} CSV rows...\n")

    # Wait for GigaB2B image fetch to complete
    giga_image_map: Dict[str, List[str]] = {}
    if giga_future is not None:
        try:
            giga_image_map = giga_future.result()
            sys.stderr.write(f"GigaB2B images fetched for {len(giga_image_map)} codes\n")
        except Exception as exc:
            sys.stderr.write(f"GigaB2B fetch failed: {exc}\n")

    out_rows: List[dict] = []
    missing_required: List[str] = []
    missing_main_color: List[str] = []
    missing_spec: List[str] = []
    score_records: List[dict] = []

    for idx, code in enumerate(present_codes):
        prod = products_map.get(code)
        if not prod:
            continue
        if (idx + 1) % 100 == 0:
            sys.stderr.write(f"  Row {idx + 1}/{len(present_codes)}\n")

        row = {k: "" for k in fieldnames}
        for k, v in template_first.items():
            if k.startswith("商品画像更新フラグ_") or k.startswith("商品画像登録有無_"):
                row[k] = v

        title = str_value(prod.get("Product Name"))
        title = apply_title_prefix(title, prod)
        desc = build_description(prod, args.description_prefix, args.description_footer)

        set_if_exists(row, "商品名", title)
        set_if_exists(row, "商品説明", desc)

        if not title or not desc:
            missing_spec.append(code)

        set_if_exists(row, "SKU1_商品管理コード", code)

        qty = str_value(prod.get("Mercari Qty"))
        price = str_value(prod.get("Mercari Effective Pricing (incl. shipping)"))
        set_if_exists(row, "販売価格", price)
        set_if_exists(row, "SKU1_在庫数", qty)
        set_if_exists(row, "SKU1_現在の在庫数", qty)

        main_color = str_value(prod.get("Representative_Color_JA"))
        sku_type = main_color if is_usable_main_color(main_color) else ""
        set_if_exists(row, "SKU1_種類", sku_type)
        if not main_color or not is_usable_main_color(main_color):
            missing_main_color.append(code)

        category = str_value(prod.get("Mercari category ID"))
        set_if_exists(row, "カテゴリID", category)

        set_if_exists(row, "商品の状態", "1")
        set_if_exists(row, "配送方法", "1")
        set_if_exists(row, "発送元の地域", "jp13")
        set_if_exists(row, "配送料の負担", "1")
        set_if_exists(row, "送料ID", "")
        set_if_exists(row, "商品ステータス", "1")

        inv_status = str_value(prod.get("Inventory Status"))
        if inv_status in ("Incoming Stock", "Restocked"):
            set_if_exists(row, "発送までの日数", "3")
        else:
            set_if_exists(row, "発送までの日数", "1")

        giga_imgs = giga_image_map.get(code, [])
        images = get_product_images(prod, giga_imgs, args.shipping_guide_url)

        for img_idx, u in enumerate(images, start=1):
            set_if_exists(row, f"商品画像名_{img_idx}", u)

        required = ["商品名", "商品説明", "販売価格", "カテゴリID"]
        miss = [k for k in required if (k in row and not str_value(row.get(k)))]
        if miss:
            missing_required.append(f"{code}: {','.join(miss)}")

        if args.score:
            score = compute_score(
                title=title,
                desc=desc,
                image_count=len(images),
                has_category=bool(category),
                price_val=num_value(price),
                has_sku_type=bool(sku_type),
                qty_val=num_value(qty),
                inv_status=inv_status,
                has_shipping_guide=any(args.shipping_guide_url in u for u in images),
                unit_price=num_value(prod.get("Unit Price")),
                discounted_price=num_value(prod.get("Discounted Unit Price")),
                spec_text=str_value(prod.get("Product Specification")),
                n_valid_images=len([u for u in images if args.shipping_guide_url not in u]),
            )
            score_records.append({"item_code": code, **score})
            if args.auto_open_qualified and score["auto_open"]:
                set_if_exists(row, "商品ステータス", "2")

        out_rows.append(row)

    out_path = args.output_path or os.path.join(os.getcwd(), f"mercari_listing_{dt.date.today().isoformat()}.csv")
    with open(out_path, "w", encoding=args.output_encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(out_rows)

    report: dict = {
        "output_path": out_path,
        "item_codes_total": len(item_codes),
        "found_in_886994": len(present_codes),
        "missing_from_886994": missing_codes,
        "rows_written": len(out_rows),
        "missing_required_fields": missing_required,
        "missing_main_color": sorted(set(missing_main_color)),
        "missing_spec": sorted(set(missing_spec)),
    }

    if args.score and score_records:
        score_out = os.path.join(os.path.dirname(out_path), f"quality_scores_{dt.date.today().isoformat()}.csv")
        score_keys = ["item_code", "total", "blocked", "auto_open", "gates"] + list(score_records[0].get("modules", {}).keys())
        with open(score_out, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=score_keys, extrasaction="ignore", lineterminator="\r\n")
            writer.writeheader()
            for sr in score_records:
                flat = {"item_code": sr["item_code"], "total": sr["total"], "blocked": sr["blocked"], "auto_open": sr["auto_open"], "gates": ";".join(sr["gates"])}
                flat.update(sr.get("modules", {}))
                writer.writerow(flat)
        report["score_output_path"] = score_out
        report["score_distribution"] = {}
        for sr in score_records:
            bucket = f"{sr['total'] // 10 * 10}-{sr['total'] // 10 * 10 + 9}"
            report["score_distribution"][bucket] = report["score_distribution"].get(bucket, 0) + 1
        report["score_auto_open_eligible"] = sum(1 for sr in score_records if sr["auto_open"])
        report["score_blocked"] = sum(1 for sr in score_records if sr["blocked"])
        report["score_gates"] = {}
        for sr in score_records:
            for g in sr["gates"]:
                report["score_gates"][g] = report["score_gates"].get(g, 0) + 1

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
