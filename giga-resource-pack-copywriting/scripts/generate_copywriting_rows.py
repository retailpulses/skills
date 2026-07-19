#!/usr/bin/env python3
# TODO(2026-07-18): Migrate from Baserow API to Supabase PostgREST.
# This script still uses api.baserow.io — update to SUPABASE_URL/rest/v1/.
# Target tables: resource_packs, platform_copy_strategies, copywriting_outputs.
# See docs/BASEROW_TO_SUPABASE_MIGRATION.md for the migration plan.
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import List, Optional, Tuple

BASEROW_API = "https://api.baserow.io/api"


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
        v = os.environ.get(key, "").strip()
        if v:
            return v
    raise SystemExit("Missing Baserow token. Pass --token or set BASEROW_TOKEN.")


def http_json(req: urllib.request.Request, timeout: int = 120):
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    return json.loads(raw)


def str_value(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ")).strip()


def strip_mg_prefix(title: str) -> str:
    s = normalize_spaces(title)
    s = re.sub(r"^【?\s*元SKU[:：]?.*?】\s*", "", s)
    s = re.sub(r"^\[?\s*元SKU[:：]?.*?\]\s*", "", s)
    s = re.sub(r"^元SKU[:：]?\s*", "", s)
    return s.strip()


def strip_control_labels(line: str) -> str:
    s = normalize_spaces(line)
    if not s:
        return ""
    s = re.sub(r"^SKU[:：]?\s*\S*\s*", "", s).strip()
    for label in ("Title", "Dimensions & Details", "Attention", "Features"):
        s = re.sub(rf"\s*{re.escape(label)}\s*$", "", s).strip()
    return s


def normalize_multiline_text(text: str, keep_blank_lines: bool = False) -> str:
    # Use compact formatting inside sections; section spacing is handled by the caller.
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines: List[str] = []
    for raw_line in raw.split("\n"):
        line = normalize_spaces(raw_line)
        if not line:
            if keep_blank_lines:
                lines.append("")
            continue
        line = re.sub(r"^[nN]\s+", "", line).strip()
        line = strip_control_labels(line)
        if not line or line in {"n", "N"}:
            continue
        if line in {"SKU", "Title", "Dimensions & Details", "Attention", "Features"}:
            continue
        if re.match(r"^SKU[:：]", line):
            continue
        lines.append(line)
    out: List[str] = []
    for line in lines:
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)
    return "\n".join(out).strip()


def fetch_table_fields(token: str, table_id: int) -> List[dict]:
    headers = {"Authorization": f"Token {token}"}
    req = urllib.request.Request(f"{BASEROW_API}/database/fields/table/{table_id}/", headers=headers)
    data = http_json(req)
    return data if isinstance(data, list) else []


def resolve_field_id(token: str, table_id: int, field_name: str) -> int:
    fields = fetch_table_fields(token, table_id)
    for f in fields:
        if str(f.get("name")) == field_name:
            return int(f["id"])
    raise SystemExit(f"Field not found in table {table_id}: {field_name}")


def fetch_rows_by_equal_filter(token: str, table_id: int, field_key: str, values: List[str]) -> List[dict]:
    headers = {"Authorization": f"Token {token}"}
    rows: List[dict] = []
    seen = set()
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
            req = urllib.request.Request(f"{BASEROW_API}/database/rows/table/{table_id}/?{query}", headers=headers)
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
                if rid in seen:
                    continue
                seen.add(rid)
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
        q = urllib.parse.urlencode({"user_field_names": "true", "size": 200, "page": page})
        req = urllib.request.Request(f"{BASEROW_API}/database/rows/table/{table_id}/?{q}", headers=headers)
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
    return sorted(set(x.strip() for x in value.split(",") if x.strip()))


def best_copy_row(rows: List[dict], item_code: str, platform: str) -> Optional[dict]:
    p = platform.lower()
    item_rows = [r for r in rows if str_value(r.get("Item Code")) == item_code]
    if not item_rows:
        return None
    target = [r for r in item_rows if str_value(r.get("Platform")).lower() == p]
    if not target:
        return None
    active = [r for r in target if bool(r.get("Active"))]
    pick = active if active else target
    pick.sort(key=lambda r: int(r.get("id") or 0), reverse=True)
    return pick[0]


def parse_mercari_prefix_footer(strategy_rows: List[dict]) -> Tuple[List[str], List[str]]:
    for row in strategy_rows:
        if str_value(row.get("Platform")).lower() != "mercari":
            continue
        text = str_value(row.get("Contents"))
        if "~~~~~~~~~~~~~~~~~" not in text:
            continue
        parts = [p.strip() for p in text.split("~~~~~~~~~~~~~~~~~")]
        if len(parts) < 3:
            continue
        prefix = [ln.strip() for ln in parts[0].splitlines() if ln.strip() and ln.strip().lower() != "prefix"]
        footer = [ln.strip() for ln in parts[2].splitlines() if ln.strip() and ln.strip().lower() != "appendix"]
        return prefix, footer
    return [], []


def build_mercari_title(product_row: dict) -> str:
    title = strip_mg_prefix(str_value(product_row.get("Product Name")))
    title = normalize_spaces(title)

    color_jp = str_value(product_row.get("Main Color (JP)")) or str_value(product_row.get("Main Color"))
    if color_jp and color_jp not in title:
        if len(f"{title} {color_jp}") <= 112:
            title = f"{title} {color_jp}"

    if len(title) <= 88:
        group = normalize_spaces(str_value(product_row.get("Giga Product Group")))
        if group and group not in title:
            if len(f"{title} {group}") <= 112:
                title = f"{title} {group}"

    if len(title) <= 96 and str_value(product_row.get("Assembly Instructions")) and "組立" not in title:
        if len(f"{title} 組立") <= 112:
            title = f"{title} 組立"

    title = normalize_spaces(title)
    if len(title) > 112:
        cut = title[:112].rstrip()
        if "【" in cut and "】" not in cut[cut.rfind("【"):]:
            cut = cut[:cut.rfind("【")].rstrip()
        elif " " in cut:
            cut = cut.rsplit(" ", 1)[0].rstrip()
        cut = cut.rstrip(" -_、】【］]")
        title = cut or title[:112].rstrip()
    return title


def build_mercari_copy_from_product(product_row: dict, strategy_rows: List[dict]) -> Tuple[str, str]:
    title = build_mercari_title(product_row)
    base_desc = normalize_multiline_text(str_value(product_row.get("Description")), keep_blank_lines=False)
    features = [normalize_spaces(str_value(product_row.get(f"Product Features {i}"))) for i in range(1, 11)]
    features = [x for x in features if x]
    length_cm = str_value(product_row.get("Package Size-Length (cm)"))
    width_cm = str_value(product_row.get("Package Size-Width (cm)"))
    height_cm = str_value(product_row.get("Package Size-Height (cm)"))
    weight_kg = str_value(product_row.get("Package Size-Weight (kg)"))
    prefix, footer = parse_mercari_prefix_footer(strategy_rows)

    lines: List[str] = []
    if prefix:
        lines.extend(normalize_multiline_text("\n".join(prefix), keep_blank_lines=False).split("\n"))
        lines.append("")
    if base_desc:
        lines.append("【商品説明】")
        lines.append(base_desc)
        lines.append("")
    if features:
        lines.append("【主な特徴】")
        for feat in features:
            lines.append(f"・{feat}")
        lines.append("")
    size_lines: List[str] = []
    if length_cm and width_cm and height_cm:
        size_lines.append(f"梱包サイズ：約 {length_cm} × {width_cm} × {height_cm} cm")
    if weight_kg:
        size_lines.append(f"梱包重量：約 {weight_kg} kg")
    if size_lines:
        lines.append("【サイズ情報】")
        lines.extend(size_lines)
        lines.append("")
    lines.append("【ご購入前にご確認ください】")
    lines.append("・モニター環境や撮影条件により、色味が実物と異なって見える場合があります。")
    lines.append("・サイズは計測方法により若干の誤差が生じる場合があります。")
    lines.append("・初期不良時は、受取評価前に取引メッセージからご連絡ください。")
    if footer:
        lines.append("")
        lines.extend(footer)
    description = "\n".join(lines).strip()
    if len(description) > 2000:
        description = description[:2000]
    return title, description


def create_copy_row(token: str, table_id: int, payload: dict) -> dict:
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASEROW_API}/database/rows/table/{table_id}/?user_field_names=true",
        headers=headers,
        data=body,
        method="POST",
    )
    return http_json(req)


def update_copy_row(token: str, table_id: int, row_id: int, payload: dict) -> dict:
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASEROW_API}/database/rows/table/{table_id}/{row_id}/?user_field_names=true",
        headers=headers,
        data=body,
        method="PATCH",
    )
    return http_json(req)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate copywriting rows in table 912536 from Item Code.")
    parser.add_argument("--item-codes", required=True, help="Comma-separated item codes or path to newline file")
    parser.add_argument("--token", default=None)
    parser.add_argument("--platform", default="mercari", choices=["mercari"])
    parser.add_argument("--product-info-table-id", type=int, default=912520)
    parser.add_argument("--strategy-table-id", type=int, default=912423)
    parser.add_argument("--copy-table-id", type=int, default=912536)
    parser.add_argument("--create-only-missing", action="store_true", default=True)
    parser.add_argument("--force-create", dest="create_only_missing", action="store_false")
    parser.add_argument("--update-existing", action="store_true", help="Update existing Mercari copy rows instead of skipping them")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)
    load_dotenv(os.path.join(skill_dir, ".env"))
    load_dotenv(os.path.join(skill_dir, ".env.local"))
    load_dotenv("/Users/user/.codex/skills/mercari-csv-listing/.env")
    load_dotenv("/Users/user/.codex/skills/mercari-csv-listing/.env.local")

    token = resolve_token(args.token)
    item_codes = parse_item_codes(args.item_codes)
    if not item_codes:
        raise SystemExit("No item codes provided")

    info_field_id = resolve_field_id(token, args.product_info_table_id, "Item Code")
    copy_field_id = resolve_field_id(token, args.copy_table_id, "Item Code")

    info_rows = fetch_rows_by_equal_filter(token, args.product_info_table_id, f"field_{info_field_id}", item_codes)
    copy_rows = fetch_rows_by_equal_filter(token, args.copy_table_id, f"field_{copy_field_id}", item_codes)
    strategy_rows = [
        r for r in fetch_all_rows(token, args.strategy_table_id)
        if bool(r.get("Active")) and str_value(r.get("Platform")).lower() in ("generic", "mercari")
    ]

    info_map = {str_value(r.get("Item Code")): r for r in info_rows}
    created = []
    updated = []
    skipped_existing = []
    missing_info = []

    for code in item_codes:
        existing = best_copy_row(copy_rows, code, args.platform)
        if existing and args.create_only_missing and not args.update_existing:
            skipped_existing.append(code)
            continue
        product = info_map.get(code)
        if not product:
            missing_info.append(code)
            continue

        title, desc = build_mercari_copy_from_product(product, strategy_rows)
        payload = {
            "Item Code": code,
            "Platform": "Mercari",
            "Active": True,
            "Title": title,
            "Description 1": desc,
            "Description 2": "",
            "Listing status": "",
        }
        if existing and args.update_existing:
            row = update_copy_row(token, args.copy_table_id, int(existing.get("id") or 0), payload)
            updated.append({"item_code": code, "row_id": row.get("id")})
        else:
            row = create_copy_row(token, args.copy_table_id, payload)
            created.append({"item_code": code, "row_id": row.get("id")})

    print(json.dumps({
        "item_codes": item_codes,
        "platform": args.platform,
        "created": created,
        "updated": updated,
        "skipped_existing": skipped_existing,
        "missing_info": missing_info,
        "counts": {
            "created": len(created),
            "updated": len(updated),
            "skipped_existing": len(skipped_existing),
            "missing_info": len(missing_info),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
