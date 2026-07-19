#!/usr/bin/env python3
"""Generate marketplace copywriting rows in Supabase from Giga Item Codes.

Reads from resource_packs + platform_copy_strategies, writes to copywriting_outputs.
Domain: product_catalog, owner: retailpulses/RPagentOS.
Replaces Baserow tables 912520, 912423, 912536.
"""
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


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


def resolve_supabase_credentials(cli_url: Optional[str], cli_key: Optional[str]):
    url = cli_url or SUPABASE_URL or os.environ.get("SUPABASE_URL", "")
    key = cli_key or SUPABASE_KEY or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("Missing Supabase credentials. Pass --supabase-url/--supabase-key or set SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY.")
    return url.rstrip("/"), key


def _headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def postgrest_get(base_url: str, key: str, table: str, params: dict = None, timeout: int = 120) -> list:
    qs = ""
    if params:
        qs = "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{base_url}/rest/v1/{table}{qs}", headers=_headers(key))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return data if isinstance(data, list) else [data]


def postgrest_post(base_url: str, key: str, table: str, payload: dict, timeout: int = 120) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h = _headers(key)
    h["Prefer"] = "return=representation"
    req = urllib.request.Request(f"{base_url}/rest/v1/{table}", headers=h, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return data[0] if isinstance(data, list) else data


def postgrest_patch(base_url: str, key: str, table: str, row_id: int, payload: dict, timeout: int = 120) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h = _headers(key)
    h["Prefer"] = "return=representation"
    req = urllib.request.Request(
        f"{base_url}/rest/v1/{table}?id=eq.{row_id}", headers=h, data=body, method="PATCH"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return data[0] if isinstance(data, list) else data


def str_value(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("　", " ")).strip()


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


def fetch_rows_by_item_codes(base_url: str, key: str, table: str, item_codes: List[str]) -> List[dict]:
    """Fetch rows from Supabase filtered by item_code values, batching to avoid URL length limits."""
    rows = []
    seen = set()
    # Supabase PostgREST supports up to ~200 values in an 'in' filter
    batch_size = 50
    for i in range(0, len(item_codes), batch_size):
        batch = item_codes[i:i + batch_size]
        # Build filter: item_code=in.(code1,code2,...)
        filter_val = ",".join(batch)
        params = {"item_code": f"in.({filter_val})", "limit": "1000"}
        for attempt in range(4):
            try:
                data = postgrest_get(base_url, key, table, params)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(1.2 * (attempt + 1))
        for row in data:
            rid = row.get("id")
            if rid in seen:
                continue
            seen.add(rid)
            rows.append(row)
    return rows


def fetch_all_rows(base_url: str, key: str, table: str) -> List[dict]:
    rows = []
    offset = 0
    limit = 200
    while True:
        params = {"select": "*", "limit": str(limit), "offset": str(offset)}
        batch = postgrest_get(base_url, key, table, params)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
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
    item_rows = [r for r in rows if str_value(r.get("item_code")) == item_code]
    if not item_rows:
        return None
    target = [r for r in item_rows if str_value(r.get("platform")).lower() == p]
    if not target:
        return None
    active = [r for r in target if r.get("is_active")]
    pick = active if active else target
    pick.sort(key=lambda r: int(r.get("id") or 0), reverse=True)
    return pick[0]


def parse_mercari_prefix_footer(strategy_rows: List[dict]) -> Tuple[List[str], List[str]]:
    for row in strategy_rows:
        if str_value(row.get("platform")).lower() != "mercari":
            continue
        text = str_value(row.get("contents")) or str_value(row.get("strategy_config"))
        if not text:
            continue
        # strategy_config may be JSON; try parsing
        if isinstance(row.get("strategy_config"), dict):
            cfg = row["strategy_config"]
            prefix = cfg.get("prefix", []) if isinstance(cfg.get("prefix"), list) else []
            footer = cfg.get("footer", []) if isinstance(cfg.get("footer"), list) else []
            if prefix or footer:
                return prefix, footer
        if "~~~~~~~~~~~~~~~~~" not in str(text):
            continue
        parts = [p.strip() for p in str(text).split("~~~~~~~~~~~~~~~~~")]
        if len(parts) < 3:
            continue
        prefix = [ln.strip() for ln in parts[0].splitlines() if ln.strip() and ln.strip().lower() != "prefix"]
        footer = [ln.strip() for ln in parts[2].splitlines() if ln.strip() and ln.strip().lower() != "appendix"]
        return prefix, footer
    return [], []


def build_mercari_title(product_row: dict) -> str:
    title = strip_mg_prefix(str_value(product_row.get("product_name")))
    title = normalize_spaces(title)

    color_jp = str_value(product_row.get("main_color_ja")) or str_value(product_row.get("main_color"))
    if color_jp and color_jp not in title:
        if len(f"{title} {color_jp}") <= 112:
            title = f"{title} {color_jp}"

    if len(title) <= 88:
        group = normalize_spaces(str_value(product_row.get("giga_product_group")))
        if group and group not in title:
            if len(f"{title} {group}") <= 112:
                title = f"{title} {group}"

    if len(title) <= 96 and str_value(product_row.get("assembly_instructions")) and "組立" not in title:
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
    base_desc = normalize_multiline_text(
        str_value(product_row.get("description") or product_row.get("product_specification")),
        keep_blank_lines=False,
    )
    features = [normalize_spaces(str_value(product_row.get(f"product_features_{i}"))) for i in range(1, 11)]
    features = [x for x in features if x]
    if not features:
        # Fallback: look for JSON product_features in resource_packs
        pack_data = product_row.get("pack_data", {})
        if isinstance(pack_data, dict):
            chars = pack_data.get("characteristics", "")
            if isinstance(chars, str) and chars:
                features = [x.strip() for x in chars.split("\n") if x.strip()]
    length_cm = str_value(product_row.get("package_length_cm"))
    width_cm = str_value(product_row.get("package_width_cm"))
    height_cm = str_value(product_row.get("package_height_cm"))
    weight_kg = str_value(product_row.get("package_weight_kg"))
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate copywriting rows in Supabase from Item Codes.")
    parser.add_argument("--item-codes", required=True, help="Comma-separated item codes or path to newline file")
    parser.add_argument("--supabase-url", default=None)
    parser.add_argument("--supabase-key", default=None)
    parser.add_argument("--platform", default="mercari", choices=["mercari"])
    parser.add_argument("--update-existing", action="store_true", help="Update existing copy rows instead of skipping them")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)
    load_dotenv(os.path.join(skill_dir, ".env"))
    load_dotenv(os.path.join(skill_dir, ".env.local"))

    base_url, key = resolve_supabase_credentials(args.supabase_url, args.supabase_key)
    item_codes = parse_item_codes(args.item_codes)
    if not item_codes:
        raise SystemExit("No item codes provided")

    # Fetch from Supabase tables
    info_rows = fetch_rows_by_item_codes(base_url, key, "resource_packs", item_codes)
    copy_rows = fetch_rows_by_item_codes(base_url, key, "copywriting_outputs", item_codes)
    strategy_rows = [
        r for r in fetch_all_rows(base_url, key, "platform_copy_strategies")
        if r.get("is_active") and str_value(r.get("platform")).lower() in ("generic", "mercari")
    ]

    info_map = {str_value(r.get("item_code")): r for r in info_rows}
    created = []
    updated = []
    skipped_existing = []
    missing_info = []

    for code in item_codes:
        existing = best_copy_row(copy_rows, code, args.platform)
        if existing and not args.update_existing:
            skipped_existing.append(code)
            continue
        product = info_map.get(code)
        if not product:
            missing_info.append(code)
            continue

        title, desc = build_mercari_copy_from_product(product, strategy_rows)
        payload = {
            "item_code": code,
            "platform": "mercari",
            "copy_text": f"Title: {title}\n\n{desc}",
        }
        if existing and args.update_existing:
            row = postgrest_patch(base_url, key, "copywriting_outputs", int(existing["id"]), payload)
            updated.append({"item_code": code, "row_id": row.get("id")})
        else:
            row = postgrest_post(base_url, key, "copywriting_outputs", payload)
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
