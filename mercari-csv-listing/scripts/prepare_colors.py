#!/usr/bin/env python3
"""Translate Main Color (EN) → Representative_Color_JA for products missing it.

Reads from Supabase baserow_886994_compat_vw, finds products where
Representative_Color_JA is empty but Main Color is set, translates via
static dict, and writes back to product_variants.

Usage:
    python3 prepare_colors.py --item-codes item_codes.txt --dry-run
    python3 prepare_colors.py --item-codes item_codes.txt
"""
import json
import os
import sys
from typing import Dict, List, Optional

from supabase_db import SupabaseDB, resolve_credentials

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
    parser.add_argument("--token", default=None, help="Supabase service_role key")
    parser.add_argument("--table-id", type=int, default=None, help="Deprecated — ignored")
    parser.add_argument("--item-codes", required=True, help="Comma-separated list or path to item-code file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    key = resolve_credentials(args.token)
    if not key:
        sys.exit("Missing Supabase key. Pass --token or set SUPABASE_SERVICE_ROLE_KEY.")
    db = SupabaseDB()

    codes = parse_item_codes_arg(args.item_codes)
    if not codes:
        print(json.dumps({"error": "No item codes provided"}, indent=2))
        return

    products = db.fetch_by_item_codes(codes)
    patches: List[dict] = []
    already_ok = 0
    no_main_color = 0
    untranslatable: List[str] = []

    for code in codes:
        r = products.get(code)
        if not r:
            continue

        rc = (r.get("Representative_Color_JA") or "").strip()
        mc = (r.get("Main Color") or "").strip()

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

        patches.append({"item_code": code, "representative_color_ja": translated})

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
            print(f"  {p['item_code']}: Representative_Color_JA → {p['representative_color_ja']}", file=sys.stderr)
        return

    print(f"Writing {len(patches)} color translations...", file=sys.stderr)
    updated = db.batch_update_variants(patches)
    errors = len(patches) - updated if updated < len(patches) else 0

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
