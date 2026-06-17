#!/usr/bin/env python3
"""Match Mercari Shops category IDs from product names and write to Baserow.

Maps 7 Shops-invalid leaf categories to their "その他" (Other) sibling.

Usage:
    python3 prepare_categories.py --item-codes item_codes.txt --dry-run
    python3 prepare_categories.py --item-codes item_codes.txt
"""
import csv
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

import requests

DEFAULT_TABLE_ID = 886994
DEFAULT_CATEGORY_MASTER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "listing-mgmt",
    "apps", "mercari-listing-tool", "public", "data", "category_master.csv",
)

# 7 leaf categories that are valid in the master CSV but NOT in Mercari Shops.
# Map them to their parent "その他" (Other) variant.
SHOPS_INVALID_LEAVES: Dict[str, str] = {
    # スポーツ > マリンスポーツ > サーフィン・ボディボード → その他
    "UVEwK2viynpxEnJebX8tmQ": "484w2yaBozF8wGeYVdmuvL",
    # ペット用品 > 猫用品 > ベッド・クッション・ハウス → その他
    "wqxANRKDMYg5cq2VTKWqQA": "ZWURFrD9jE96QKfxrHfqqF",
    # フラワー・ガーデニング > 園芸用品 > ガーデンファニチャー → その他
    "h6BkKCPeBWFQYkBUVartEa": "CBtfuJn7pMEb3QkkkYbvdY",
    # ゲーム・おもちゃ・グッズ > おもちゃ > 大型遊具・室内遊具 → その他
    "qHynx7SDgbFBdtS6QngV7d": "RCVuRU7Ru3xvBFY6vr5xP7",
    # DIY・工具 > 住宅設備 > 物置・車庫 → その他
    "Vryr7c8QcED4887tVf9tKj": "DkjqZAKBXaZN8FB2Kb6zhX",
    # 家具・インテリア > ベッド・マットレス > マットレス → その他
    "Wa4K4gTeK7qkkAq2RurqJL": "pACXAgkow3q7TJUqqm7xt3",
    # 家具・インテリア > 寝具 > 布団・毛布 → その他
    "EgvVSoyHsEnpaHyNZoGNcc": "Yqwn6Tc8stTxsR9iFZf3Tk",
}


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


def load_category_master(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            {"id": r["カテゴリID"], "name": r["カテゴリ名"], "full": r["カテゴリ名（フル）"]}
            for r in reader
        ]


def build_category_rules(categories: List[dict]) -> List[Tuple[List[str], str]]:
    full_path_map = {c["full"]: c["id"] for c in categories}

    keyword_rules = [
        (["猫タワー"], "ペット用品 > 猫用品 > ベッド・クッション・ハウス"),
        (["キャットタワー"], "ペット用品 > 猫用品 > ベッド・クッション・ハウス"),
        (["サップボード", "supボード", "パドルボード"], "スポーツ > マリンスポーツ > サーフィン・ボディボード"),
        (["人工芝"], "フラワー・ガーデニング > 園芸用品 > ガーデンファニチャー"),
        (["滑り台", "すべり台", "ジャングルジム", "室内遊具", "キッズパーク"], "ゲーム・おもちゃ・グッズ > おもちゃ > 大型遊具・室内遊具"),
        (["三輪車"], "ベビー・キッズ > 外出・移動用品 > ベビーカー・バギー"),
        (["プール", "ビニールプール", "エアープール", "水鉄砲"], "アウトドア・釣り・旅行用品 > アウトドア > 水遊び"),
        (["トランポリン"], "スポーツ > その他スポーツ > エクササイズ用品"),
        (["ガーデンカート", "カゴ台車", "台車", "キャリーカー", "手押し台車", "運搬車"], "DIY・工具 > 台車"),
        (["カーポート", "車庫", "ガレージ", "物置"], "DIY・工具 > 住宅設備 > 物置・車庫"),
        (["ソファベッド", "ソファ ベッド", "ソファー ベッド"], "家具・インテリア > ソファ・ソファベッド > ソファベッド"),
        (["ローソファ", "フロアソファ"], "家具・インテリア > ソファ・ソファベッド > ローソファ/フロアソファ"),
        (["2人掛けソファ", "3人掛けソファ"], "家具・インテリア > ソファ・ソファベッド > 2人掛け・3人掛けソファ"),
        (["1人掛けソファ", "一人掛けソファ"], "家具・インテリア > ソファ・ソファベッド > 1人掛けソファ"),
        (["コーナーソファ"], "家具・インテリア > ソファ・ソファベッド > コーナーソファ"),
        (["ソファ", "ソファー"], "家具・インテリア > ソファ・ソファベッド > その他"),
        (["オフィスチェア", "ワークチェア", "パソコンチェア"], "家具・インテリア > 椅子・チェア > オフィスチェア・ワークチェア"),
        (["ゲーミングチェア"], "家具・インテリア > 椅子・チェア > ゲーミングチェア"),
        (["ダイニングチェア"], "家具・インテリア > 椅子・チェア > ダイニングチェア"),
        (["座椅子"], "家具・インテリア > 椅子・チェア > 座椅子"),
        (["折り畳みイス", "折りたたみイス", "折り畳み椅子"], "家具・インテリア > 椅子・チェア > 折り畳みイス"),
        (["スツール"], "家具・インテリア > 椅子・チェア > スツール"),
        (["ベンチ"], "家具・インテリア > 椅子・チェア > ベンチ"),
        (["イームズチェア"], "家具・インテリア > 椅子・チェア > ダイニングチェア"),
        (["チェア", "椅子", "いす", "イス"], "家具・インテリア > 椅子・チェア > 椅子"),
        (["パソコンデスク", "pcデスク", "pc デスク"], "家具・インテリア > 机・テーブル > パソコンデスク"),
        (["ダイニングテーブル"], "家具・インテリア > 机・テーブル > ダイニングテーブル"),
        (["サイドテーブル", "ナイトテーブル"], "家具・インテリア > 机・テーブル > サイドテーブル・ナイトテーブル・ローテーブル"),
        (["ローテーブル", "センターテーブル"], "家具・インテリア > 机・テーブル > センターテーブル・ローテーブル"),
        (["事務机", "学習机"], "家具・インテリア > 机・テーブル > 事務机・学習机"),
        (["こたつ"], "家具・インテリア > 机・テーブル > こたつ"),
        (["デスク", "机", "テーブル"], "家具・インテリア > 机・テーブル > その他"),
        (["マットレス"], "家具・インテリア > ベッド・マットレス > マットレス"),
        (["折りたたみベッド"], "家具・インテリア > ベッド・マットレス > 簡易ベッド・折りたたみベッド"),
        (["二段ベッド"], "家具・インテリア > ベッド・マットレス > 二段ベッド"),
        (["ベッドフレーム"], "家具・インテリア > ベッド・マットレス > ベッドフレーム"),
        (["ロフトベッド"], "家具・インテリア > ベッド・マットレス > ロフトベッド・システムベッド"),
        (["ベッド"], "家具・インテリア > ベッド・マットレス > その他"),
        (["スチールラック", "メタルラック"], "家具・インテリア > 棚・ラック・シェルフ > スチールラック・メタルラック"),
        (["本棚"], "家具・インテリア > 棚・ラック・シェルフ > 本棚・本収納"),
        (["カラーボックス"], "家具・インテリア > リビング収納 > カラーボックス"),
        (["テレビ台", "テレビボード"], "家具・インテリア > リビング収納 > テレビ台"),
        (["キャビネット", "サイドボード"], "家具・インテリア > リビング収納 > キャビネット・サイドボード"),
        (["ドレッサー", "鏡台"], "家具・インテリア > リビング収納 > ドレッサー・鏡台"),
        (["シューズラック", "下駄箱", "靴箱"], "家具・インテリア > 玄関・屋外収納 > 下駄箱・靴箱・シューズラック"),
        (["チェスト"], "家具・インテリア > 洋服タンス・押入れ収納 > チェスト・タンス"),
        (["ハンガーラック"], "家具・インテリア > 洋服タンス・押入れ収納 > ハンガーラック・ポールハンガー"),
        (["パーテーション", "間仕切り"], "家具・インテリア > リビング収納 > 間仕切り・パーテーション"),
        (["ラック", "シェルフ", "棚"], "家具・インテリア > 棚・ラック・シェルフ > その他"),
        (["収納"], "家具・インテリア > 収納家具"),
        (["ケース", "ボックス", "コンテナ"], "家具・インテリア > ケース・ボックス・コンテナ"),
        (["ラグ", "カーペット"], "家具・インテリア > ラグ・カーペット・マット > ラグ・カーペット"),
        (["マット"], "家具・インテリア > ラグ・カーペット・マット > マット"),
        (["ジョイントマット"], "家具・インテリア > ラグ・カーペット・マット > ジョイントマット"),
        (["デスクライト", "テーブルライト"], "家具・インテリア > ライト・照明 > テーブルライト・デスクライト"),
        (["シーリングライト"], "家具・インテリア > ライト・照明 > シーリングライト・天井照明"),
        (["フロアスタンド"], "家具・インテリア > ライト・照明 > フロアスタンド"),
        (["照明", "ライト", "ランプ"], "家具・インテリア > ライト・照明 > その他"),
        (["カーテン"], "家具・インテリア > カーテン・ブラインド > カーテン"),
        (["ブラインド"], "家具・インテリア > カーテン・ブラインド > ブラインド"),
        (["キッチンワゴン"], "家具・インテリア > キッチン収納 > キッチンワゴン"),
        (["食器棚", "キッチンカウンター"], "家具・インテリア > キッチン収納 > 食器棚・キッチンカウンター"),
        (["ランドリーラック", "洗濯機ラック"], "家具・インテリア > バス・トイレ収納 > ランドリーラック・洗濯機ラック"),
        (["トイレ収納"], "家具・インテリア > バス・トイレ収納 > トイレ収納"),
        (["傘立て"], "家具・インテリア > 玄関・屋外収納 > 傘立て"),
        (["枕"], "家具・インテリア > 寝具 > 枕"),
        (["布団", "毛布"], "家具・インテリア > 寝具 > 布団・毛布"),
        (["シーツ", "カバー"], "家具・インテリア > 寝具 > シーツ・カバー"),
        (["寝具"], "家具・インテリア > 寝具 > その他"),
        (["クッション", "座布団"], "家具・インテリア > インテリア小物 > クッション・座布団"),
        (["鏡"], "家具・インテリア > インテリア小物 > 鏡"),
        (["ごみ箱", "ゴミ箱", "くず箱", "ダストボックス"], "家具・インテリア > インテリア小物 > ごみ箱"),
        (["ティッシュボックス", "ティッシュケース"], "家具・インテリア > インテリア小物 > ティッシュボックス"),
        (["収納庫", "ガーデニング"], "フラワー・ガーデニング > 園芸用品 > ガーデンファニチャー"),
        (["スーツケース", "キャリーケース", "キャリーバッグ"], "アウトドア・釣り・旅行用品 > 旅行用品 > 旅行用バッグ・荷物"),
        (["キッチン"], "キッチン・日用品・その他 > キッチン・食器 > その他"),
        (["工具", "工具セット", "ドライバー", "レンチ"], "DIY・工具 > 電動工具・エア工具 > その他"),
        (["収納ボックス", "収納ケース"], "家具・インテリア > ケース・ボックス・コンテナ"),
        (["洗濯機"], "生活家電・空調 > 生活家電 > 洗濯機"),
        (["冷蔵庫"], "生活家電・空調 > 生活家電 > 冷蔵庫"),
        (["掃除機", "ロボット掃除機"], "生活家電・空調 > 生活家電 > 掃除機"),
        (["洗濯"], "キッチン・日用品・その他 > 洗濯用品 > その他"),
        (["小物入れ"], "家具・インテリア > インテリア小物 > 小物入れ"),
    ]

    rules = []
    seen_ids = set()
    for keywords, full_path in keyword_rules:
        cid = full_path_map.get(full_path)
        if cid and cid not in seen_ids:
            rules.append((keywords, cid))
            seen_ids.add(cid)
    return rules


def apply_shops_fallback(cid: str) -> str:
    return SHOPS_INVALID_LEAVES.get(cid, cid)


def match_category(product_name: str, rules: List[Tuple[List[str], str]]) -> Optional[str]:
    if not product_name:
        return None
    name_flat = product_name.lower().replace(" ", "").replace("\u3000", "")
    for keywords, cid in rules:
        for kw in keywords:
            kw_flat = kw.lower().replace(" ", "").replace("\u3000", "")
            if kw_flat in name_flat:
                return cid
    return None


def fetch_products_by_codes(session: requests.Session, token: str, table_id: int, codes: List[str]) -> Dict[str, dict]:
    result = {}
    api = "https://api.baserow.io/api"
    for code in codes:
        url = f"{api}/database/rows/table/{table_id}/?user_field_names=true&filter__field_7670234__equal={code}"
        try:
            resp = session.get(url, headers={"Authorization": f"Token {token}"}, timeout=30)
            data = resp.json()
            for r in data.get("results", []):
                result[code] = r
        except Exception as exc:
            print(f"  WARN: failed to fetch {code}: {exc}", file=sys.stderr)
        time.sleep(0.08)
    return result


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Match Mercari Shops category IDs and write to Baserow")
    parser.add_argument("--token", default=None)
    parser.add_argument("--table-id", type=int, default=DEFAULT_TABLE_ID)
    parser.add_argument("--item-codes", required=True, help="Comma-separated list or path to item-code file")
    parser.add_argument("--category-master-path", default=DEFAULT_CATEGORY_MASTER)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    token = resolve_token(args.token)
    table_id = args.table_id
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {token}", "User-Agent": "Retailpulses-PrepareCategories/1.0"})

    codes = parse_item_codes_arg(args.item_codes)
    if not codes:
        print(json.dumps({"error": "No item codes provided"}, indent=2))
        return

    master_path = args.category_master_path
    if not os.path.isfile(master_path):
        print(f"ERROR: category master not found at {master_path}", file=sys.stderr)
        return

    print(f"Loading categories from {master_path}...", file=sys.stderr)
    categories = load_category_master(master_path)
    print(f"Loaded {len(categories)} categories", file=sys.stderr)

    rules = build_category_rules(categories)
    print(f"Built {len(rules)} matching rules", file=sys.stderr)

    print(f"Fetching {len(codes)} products from table {table_id}...", file=sys.stderr)
    products = fetch_products_by_codes(session, token, table_id, codes)
    print(f"Fetched {len(products)} products", file=sys.stderr)

    unmatched = []
    patches: List[dict] = []
    total_with_existing = 0
    total_matched = 0
    total_fallback = 0

    for code in codes:
        prod = products.get(code)
        if not prod:
            unmatched.append(code)
            continue

        current_cat = (prod.get("Mercari category ID") or "").strip()
        if current_cat:
            if current_cat in SHOPS_INVALID_LEAVES:
                fixed_cid = SHOPS_INVALID_LEAVES[current_cat]
                pid = prod.get("id")
                if pid:
                    patches.append({"id": pid, "Mercari category ID": fixed_cid})
                    total_fallback += 1
                total_matched += 1
            else:
                total_with_existing += 1
            continue

        name = prod.get("Product Name") or ""
        cid = match_category(name, rules)
        if not cid:
            unmatched.append(code)
            continue

        fallback_cid = apply_shops_fallback(cid)
        if fallback_cid != cid:
            total_fallback += 1

        pid = prod.get("id")
        if pid:
            patches.append({"id": pid, "Mercari category ID": fallback_cid})
            total_matched += 1

    print(f"\nResults:", file=sys.stderr)
    print(f"  Already have valid category ID: {total_with_existing}", file=sys.stderr)
    print(f"  Fixed/assigned: {total_matched} ({total_fallback} Shops-safe fallback applied)", file=sys.stderr)
    print(f"  Unmatched: {len(unmatched)}", file=sys.stderr)

    if unmatched:
        print(f"\nUnmatched codes:", file=sys.stderr)
        for c in unmatched:
            print(f"  {c}", file=sys.stderr)

    if not patches:
        print("\nNothing to update.", file=sys.stderr)
        return

    if args.dry_run:
        print(f"\nDRY RUN: would update {len(patches)} rows", file=sys.stderr)
        for p in patches[:5]:
            print(f"  row {p['id']}: category ID → {p['Mercari category ID']}", file=sys.stderr)
        if len(patches) > 5:
            print(f"  ... and {len(patches) - 5} more", file=sys.stderr)
        output_summary = {
            "dry_run": True,
            "total_codes": len(codes),
            "already_have_category": total_with_existing,
            "new_matches": total_matched,
            "shops_fallback_applied": total_fallback,
            "unmatched": len(unmatched),
            "unmatched_codes": unmatched,
            "would_update": len(patches),
        }
        print(json.dumps(output_summary, ensure_ascii=False, indent=2))
        return

    api = "https://api.baserow.io/api"
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
        "already_have_category": total_with_existing,
        "new_matches": total_matched,
        "shops_fallback_applied": total_fallback,
        "unmatched": len(unmatched),
        "unmatched_codes": unmatched,
        "updated_rows": updated,
        "batch_errors": errors,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
