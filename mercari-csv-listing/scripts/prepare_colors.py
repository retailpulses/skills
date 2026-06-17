#!/usr/bin/env python3
"""Translate Main Color (EN) → Representative_Color_JA for products missing it.

Reads Baserow table 886994, finds products where Representative_Color_JA is
empty but Main Color is set, translates via static dict, and writes back.

Usage:
    python3 prepare_colors.py --item-codes item_codes.txt --dry-run
    python3 prepare_colors.py --item-codes item_codes.txt
"""
import json
import os
import sys
import time
from typing import Dict, List, Optional

import requests

EN_TO_JA: Dict[str, str] = {
    "black": "ブラック",
    "white": "ホワイト",
    "grey": "グレー",
    "gray": "グレー",
    "beige": "ベージュ",
    "brown": "ブラウン",
    "dark brown": "ダークブラウン",
    "light brown": "ライトブラウン",
    "dark grey": "ダークグレー",
    "dark gray": "ダークグレー",
    "light grey": "ライトグレー",
    "light gray": "ライトグレー",
    "silver grey": "シルバーグレー",
    "silver": "シルバー",
    "red": "レッド",
    "blue": "ブルー",
    "navy blue": "ネイビー",
    "light blue": "ライトブルー",
    "green": "グリーン",
    "light green": "ライトグリーン",
    "yellow": "イエロー",
    "mustard yellow": "マスタードイエロー",
    "orange": "オレンジ",
    "pink": "ピンク",
    "purple": "パープル",
    "ivory": "アイボリー",
    "natural": "ナチュラル",
    "natural wood": "ナチュラルウッド",
    "wood": "ウッド",
    "dark wood": "ダークウッド",
    "black pu": "ブラックPU",
    "pink epu": "ピンクEPU",
    "neutral": "ニュートラル",
    "cream": "クリーム",
    "wine red": "ワインレッド",
    "gold": "ゴールド",
    "khaki": "カーキ",
    "charcoal": "チャコール",
    "off white": "オフホワイト",
    "clear": "クリア",
    "transparent": "クリア",
    "camel": "キャメル",
    "greige": "グレージュ",
    "colorful": "カラフル",
    "coffee": "コーヒー",
    "grey+white": "グレー+ホワイト",
    "gray+beige": "グレー+ベージュ",
    "white+black": "ホワイト+ブラック",
    "white,white+purple": "ホワイト+パープル",
    "blue+grey": "ブルー+グレー",
    "blue+gray": "ブルー+グレー",
}


def translate_color(en: str) -> Optional[str]:
    s = en.strip().lower()
    if s in EN_TO_JA:
        return EN_TO_JA[s]

    parts = re.split(r"\s*[\+/]\s*", s)
    translated = []
    for p in parts:
        p = p.strip()
        if p in EN_TO_JA:
            translated.append(EN_TO_JA[p])
        elif p:
            if "+" in en or "/" in en:
                translated.append(p.capitalize())
            else:
                return None
    return "+".join(translated) if translated else None


import re


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


def parse_item_codes_arg(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    raw = raw.strip()
    if os.path.isfile(raw):
        with open(raw, "r", encoding="utf-8") as f:
            codes = [l.strip() for l in f if l.strip()]
        return codes if codes else None
    parts = [c.strip() for c in raw.split(",") if c.strip()]
    return parts if parts else None


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Backfill Representative_Color_JA from Main Color")
    parser.add_argument("--token", default=None)
    parser.add_argument("--table-id", type=int, default=886994)
    parser.add_argument("--item-codes", required=True, help="Comma-separated list or path to item-code file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    token = resolve_token(args.token)
    table_id = args.table_id
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {token}", "User-Agent": "Retailpulses-PrepareColors/1.0"})

    codes = parse_item_codes_arg(args.item_codes)
    if not codes:
        print(json.dumps({"error": "No item codes provided"}, indent=2))
        return

    api = "https://api.baserow.io/api"
    patches: List[dict] = []
    already_ok = 0
    no_main_color = 0
    untranslatable: List[str] = []

    for code in codes:
        url = f"{api}/database/rows/table/{table_id}/?user_field_names=true&filter__field_7670234__equal={code}"
        try:
            resp = session.get(url, timeout=30)
            data = resp.json()
        except Exception as exc:
            print(f"  WARN: failed to fetch {code}: {exc}", file=sys.stderr)
            continue

        for r in data.get("results", []):
            rc = (r.get("Representative_Color_JA") or "").strip()
            mc = (r.get("Main Color") or "").strip()
            pid = r.get("id")

            if rc:
                already_ok += 1
                continue

            if not mc:
                no_main_color += 1
                continue

            translated = translate_color(mc)
            if not translated:
                untranslatable.append(f"{code}: {mc}")
                continue

            if pid:
                patches.append({"id": pid, "Representative_Color_JA": translated})

        time.sleep(0.08)

    print(f"Results:", file=sys.stderr)
    print(f"  Already have Representative_Color_JA: {already_ok}", file=sys.stderr)
    print(f"  No Main Color either: {no_main_color}", file=sys.stderr)
    print(f"  To update: {len(patches)}", file=sys.stderr)
    print(f"  Untranslatable: {len(untranslatable)}", file=sys.stderr)
    if untranslatable:
        for u in untranslatable[:10]:
            print(f"    {u}", file=sys.stderr)

    if not patches:
        print("\nNothing to update.", file=sys.stderr)
        return

    if args.dry_run:
        print(f"\nDRY RUN: would update {len(patches)} rows", file=sys.stderr)
        for p in patches[:5]:
            print(f"  row {p['id']}: Representative_Color_JA → {p['Representative_Color_JA']}", file=sys.stderr)
        return

    batch_url = f"{api}/database/rows/table/{table_id}/batch/?user_field_names=true"
    updated = 0
    errors = 0

    for i in range(0, len(patches), 100):
        batch = patches[i : i + 100]
        try:
            resp = session.patch(batch_url, json={"items": batch}, timeout=60)
            if resp.status_code in (200, 201):
                updated += len(batch)
            else:
                errors += len(batch)
                print(f"  Batch error at offset {i}: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        except Exception as exc:
            errors += len(batch)
            print(f"  Batch exception at offset {i}: {exc}", file=sys.stderr)
        time.sleep(0.3)

    output = {
        "dry_run": False,
        "total_codes": len(codes),
        "already_ok": already_ok,
        "no_main_color": no_main_color,
        "updated": updated,
        "untranslatable": len(untranslatable),
        "batch_errors": errors,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
