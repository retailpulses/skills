#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import shlex
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

GRAPHQL_ENDPOINT = "https://api.mercari-shops.com/v1/graphql"

QUERY_PRODUCT_VARIANT_BY_SKU = """
query productVariant($by: ProductVariantBy!) {
  productVariant(by: $by) {
    id
    skuCode
    stockQuantity
    product {
      id
      name
      status
    }
  }
}
""".strip()

MUTATION_CREATE_PRODUCT = """
mutation createProduct($input: CreateProductInput!) {
  createProduct(input: $input) {
    product {
      id
      name
      status
      variants {
        id
        skuCode
        stockQuantity
      }
    }
  }
}
""".strip()

QUERY_SHIPPING_CONFIGS = """
query productShippingConfigurations($first: Int!) {
  productShippingConfigurations(first: $first) {
    edges {
      node {
        id
        displayId
        title
        type
      }
    }
  }
}
""".strip()

QUERY_SHIPPING_CONFIGS_PAGED = """
query productShippingConfigurations($first: Int!, $after: String) {
  productShippingConfigurations(first: $first, after: $after) {
    edges {
      node {
        id
        displayId
        title
        type
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
""".strip()


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def parse_csv(path: Path) -> List[dict]:
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except Exception:
            continue
    raise RuntimeError(f"Unable to decode CSV: {path}")


def csv_int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def pick_images(row: dict) -> List[str]:
    out: List[str] = []
    for i in range(1, 21):
        k = f"商品画像名_{i}"
        u = str(row.get(k) or "").strip()
        if u:
            out.append(u)
    return out


def map_condition(csv_val: str) -> str:
    # Mercari CSV state uses numeric codes; map to API enum with conservative defaults.
    mapping = {
        "1": "BRAND_NEW",
        "2": "ALMOST_NEW",
        "3": "CLEAN",
        "4": "LITTLE_DIRTY",
        "5": "DIRTY",
        "6": "BAD",
    }
    return mapping.get(str(csv_val).strip(), "BRAND_NEW")


def map_shipping_duration(csv_val: str) -> str:
    v = str(csv_val).strip()
    mapping = {
        "1": "ONE_TO_TWO_DAYS",
        "2": "TWO_TO_THREE_DAYS",
        "3": "FOUR_TO_SEVEN_DAYS",
        "4": "FOUR_TO_SEVEN_DAYS",
        "5": "FOUR_TO_SEVEN_DAYS",
    }
    return mapping.get(v, "ONE_TO_TWO_DAYS")


def map_shipping_method(csv_val: str) -> str:
    # Current skill output uses fixed value `1`; map to API enum per existing SOP baseline.
    _ = csv_val
    return "UNDECIDED"


def map_shipping_payer(csv_val: str) -> str:
    # Current listing workflow uses buyer-paid shipping with a shipping config ID.
    _ = csv_val
    return "BUYER"


def map_status(csv_val: str) -> str:
    v = str(csv_val).strip()
    if v == "1":
        return "UNOPENED"
    return "OPENED"


def build_create_input(row: dict, shipping_configuration_id: str) -> dict:
    sku = str(row.get("SKU1_商品管理コード") or "").strip()
    variant_name = str(row.get("SKU1_種類") or "").strip()
    name = str(row.get("商品名") or "").strip()[:120]
    desc = str(row.get("商品説明") or "").strip()[:2000]
    price = csv_int(row.get("販売価格"), default=0)
    stock = csv_int(row.get("SKU1_在庫数") or row.get("SKU1_現在の在庫数"), default=0)

    data = {
        "categoryId": str(row.get("カテゴリID") or "").strip(),
        "condition": map_condition(row.get("商品の状態")),
        "description": desc,
        # Keep payload conservative for API stability.
        # Mercari listing CSV and API upload should keep the full image set
        # aligned with the current template limit.
        "imageUrls": pick_images(row)[:20],
        "name": name,
        "price": price,
        "shippingDuration": map_shipping_duration(row.get("発送までの日数")),
        "shippingFromStateId": str(row.get("発送元の地域") or "jp13").strip() or "jp13",
        "shippingMethod": map_shipping_method(row.get("配送方法")),
        "shippingPayer": map_shipping_payer(row.get("配送料の負担")),
        "shippingConfigurationId": shipping_configuration_id,
        "status": map_status(row.get("商品ステータス")),
        "variants": [
            {
                "skuCode": sku,
                "stockQuantity": stock,
                **({"name": variant_name} if variant_name else {}),
            }
        ],
    }

    # Remove empty keys that can trigger API validation failures.
    clean = {k: v for k, v in data.items() if v not in (None, "", [], {})}
    return clean


def validate_row_payload(row: dict) -> List[str]:
    miss = []
    checks = {
        "SKU1_商品管理コード": "sku",
        "商品名": "name",
        "商品説明": "description",
        "販売価格": "price",
        "カテゴリID": "categoryId",
        "発送元の地域": "shippingFromStateId",
        "送料ID": "shippingConfigurationId",
    }
    for key in checks:
        if not str(row.get(key) or "").strip():
            miss.append(key)
    if not pick_images(row):
        miss.append("商品画像名_1..20")
    return miss


def fetch_shipping_config_map(
    token: str,
    host: str,
    ssh_key: str,
    ua_name: str,
    ua_version: str,
) -> Dict[str, str]:
    out: Dict[str, str] = {}
    after = None
    while True:
        body = graphql_call(
            mode="ssh",
            host=host,
            ssh_key=ssh_key,
            token=token,
            ua_name=ua_name,
            ua_version=ua_version,
            query=QUERY_SHIPPING_CONFIGS_PAGED,
            variables={"first": 100, "after": after},
        )
        if body.get("errors"):
            raise RuntimeError(
                f"shipping config lookup failed: {json.dumps(body['errors'], ensure_ascii=False)}"
            )
        conn = ((body.get("data") or {}).get("productShippingConfigurations") or {})
        for edge in conn.get("edges") or []:
            node = edge.get("node") or {}
            display_id = str(node.get("displayId") or "").strip()
            cfg_id = str(node.get("id") or "").strip()
            if display_id and cfg_id:
                out[display_id] = cfg_id
        pi = conn.get("pageInfo") or {}
        if not pi.get("hasNextPage"):
            break
        after = pi.get("endCursor")
        if not after:
            break
    return out


def graphql_direct(token: str, user_agent: str, query: str, variables: Optional[dict]) -> dict:
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    req = urllib.request.Request(
        GRAPHQL_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def graphql_via_ssh(
    host: str,
    ssh_key: str,
    token: str,
    user_agent_name: str,
    user_agent_version: str,
    query: str,
    variables: Optional[dict],
) -> dict:
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    payload_json = json.dumps(payload, ensure_ascii=False)
    remote_cmd = (
        f"export MERCARI_ACCESS_TOKEN={shlex.quote(token)} "
        f"MERCARI_API_CLIENT_NAME={shlex.quote(user_agent_name)} "
        f"MERCARI_API_CLIENT_VERSION={shlex.quote(user_agent_version)}; "
        "curl -4 -sS -X POST 'https://api.mercari-shops.com/v1/graphql' "
        "-H \"Authorization: Bearer $MERCARI_ACCESS_TOKEN\" "
        "-H 'Content-Type: application/json' "
        "-H \"User-Agent: $MERCARI_API_CLIENT_NAME/$MERCARI_API_CLIENT_VERSION\" "
        "--data-binary @-"
    )

    last_err = None
    for attempt in range(1, 4):
        proc = subprocess.run(
            ["ssh", "-i", ssh_key, "-o", "BatchMode=yes", host, remote_cmd],
            input=payload_json,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            out = (proc.stdout or "").strip()
            if not out:
                last_err = "empty ssh stdout"
            else:
                try:
                    return json.loads(out)
                except json.JSONDecodeError:
                    last_err = out[:500]
        last_err = (proc.stderr or proc.stdout or "").strip()
        if attempt < 3:
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"ssh/curl failed: {last_err}")


def graphql_call(
    mode: str,
    host: str,
    ssh_key: str,
    token: str,
    ua_name: str,
    ua_version: str,
    query: str,
    variables: Optional[dict],
) -> dict:
    if mode == "direct":
        return graphql_direct(token, f"{ua_name}/{ua_version}", query, variables)
    return graphql_via_ssh(host, ssh_key, token, ua_name, ua_version, query, variables)


def parse_shops(shops_arg: str) -> List[str]:
    out = [s.strip().lower() for s in shops_arg.split(",") if s.strip()]
    return out


def resolve_shop_tokens(shop_keys: List[str]) -> Dict[str, str]:
    token_map = {}
    for key in shop_keys:
        env_key = f"MERCARI_{key.upper()}_TOKEN"
        tok = os.environ.get(env_key, "").strip()
        if tok:
            token_map[key] = tok
    return token_map


def parse_tokens_private_md(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    out: Dict[str, str] = {}
    # Match blocks like:
    # ## Shop1
    # - API token: `msp_...`
    pattern = re.compile(
        r"##\s*Shop(\d+).*?API token:\s*`([^`]+)`",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(text):
        shop_num = m.group(1)
        token = m.group(2).strip()
        if token:
            out[f"shop{shop_num}"] = token
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Mercari listing CSV to multi shops via API with SKU skip-if-exists.")
    parser.add_argument("--csv", required=True, help="Final Mercari CSV path")
    parser.add_argument("--shops", default="shop1,shop2,shop3,shop4", help="Comma-separated shop keys")
    parser.add_argument("--mode", choices=["ssh", "direct"], default="ssh", help="API execution mode")
    parser.add_argument("--ssh-host", default="root@160.251.141.110")
    parser.add_argument("--ssh-key", default=str(Path.home() / ".ssh" / "id_ed25519"))
    parser.add_argument("--user-agent-name", default="Inhouse_ERP")
    parser.add_argument("--user-agent-version", default="0.0.1")
    parser.add_argument("--sleep-ms", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-json", default=None)
    parser.add_argument(
        "--tokens-private-md",
        default="/Users/user/Documents/April 2026/Mercari API testing/knowledge/Mercari_API_Tokens_Private_2026-04-01.md",
        help="Optional markdown file path that contains Shop1..4 API tokens.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    load_dotenv(skill_dir / ".env")
    load_dotenv(skill_dir / ".env.local")

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    shop_keys = parse_shops(args.shops)
    if not shop_keys:
        raise SystemExit("No shops provided")

    token_map = resolve_shop_tokens(shop_keys)
    if len(token_map) < len(shop_keys):
        file_tokens = parse_tokens_private_md(Path(args.tokens_private_md))
        for k in shop_keys:
            if k not in token_map and k in file_tokens:
                token_map[k] = file_tokens[k]
    missing_keys = [k for k in shop_keys if k not in token_map]
    if missing_keys:
        missing_env = [f"MERCARI_{k.upper()}_TOKEN" for k in missing_keys]
        raise SystemExit(
            "Missing tokens for shops: "
            + ",".join(missing_keys)
            + ". Set env vars "
            + ",".join(missing_env)
            + f" or provide --tokens-private-md with these shop tokens."
        )
    rows = parse_csv(csv_path)

    started_at = datetime.utcnow().isoformat() + "Z"
    results = []

    for shop in shop_keys:
        token = token_map[shop]
        shipping_config_map = fetch_shipping_config_map(
            token,
            args.ssh_host,
            args.ssh_key,
            args.user_agent_name,
            args.user_agent_version,
        )
        for idx, row in enumerate(rows, start=1):
            sku = str(row.get("SKU1_商品管理コード") or "").strip()
            shipping_display_id = str(row.get("送料ID") or "").strip()
            rec = {
                "shop": shop,
                "row_index": idx,
                "sku": sku,
                "shipping_display_id": shipping_display_id,
            }

            if args.dry_run:
                rec["status"] = "dry_run"
                rec["action"] = "would_check_and_create"
                results.append(rec)
                continue

            # 1) pre-check existing by sku
            if not sku:
                rec["status"] = "invalid"
                rec["missing"] = ["SKU1_商品管理コード"]
                results.append(rec)
                continue
            check_resp = graphql_call(
                mode=args.mode,
                host=args.ssh_host,
                ssh_key=args.ssh_key,
                token=token,
                ua_name=args.user_agent_name,
                ua_version=args.user_agent_version,
                query=QUERY_PRODUCT_VARIANT_BY_SKU,
                variables={"by": {"skuCode": sku}},
            )

            existing = ((check_resp.get("data") or {}).get("productVariant") or None)
            if existing and existing.get("id"):
                rec["status"] = "skipped_existing"
                rec["product_variant_id"] = existing.get("id")
                rec["product_id"] = ((existing.get("product") or {}).get("id"))
                results.append(rec)
                if args.sleep_ms > 0:
                    time.sleep(args.sleep_ms / 1000)
                continue

            # 2) createProduct
            missing = validate_row_payload(row)
            if missing:
                rec["status"] = "invalid"
                rec["missing"] = missing
                results.append(rec)
                continue
            shipping_configuration_id = shipping_config_map.get(shipping_display_id, "")
            if not shipping_configuration_id:
                rec["status"] = "invalid"
                rec["missing"] = ["shippingConfigurationId"]
                results.append(rec)
                continue
            input_payload = build_create_input(row, shipping_configuration_id)
            create_resp = graphql_call(
                mode=args.mode,
                host=args.ssh_host,
                ssh_key=args.ssh_key,
                token=token,
                ua_name=args.user_agent_name,
                ua_version=args.user_agent_version,
                query=MUTATION_CREATE_PRODUCT,
                variables={"input": input_payload},
            )

            # 3) mandatory verification by sku (even if create had errors)
            verify_resp = graphql_call(
                mode=args.mode,
                host=args.ssh_host,
                ssh_key=args.ssh_key,
                token=token,
                ua_name=args.user_agent_name,
                ua_version=args.user_agent_version,
                query=QUERY_PRODUCT_VARIANT_BY_SKU,
                variables={"by": {"skuCode": sku}},
            )
            verified = ((verify_resp.get("data") or {}).get("productVariant") or None)

            if verified and verified.get("id"):
                rec["status"] = "created_or_exists_after_create"
                rec["product_variant_id"] = verified.get("id")
                rec["product_id"] = ((verified.get("product") or {}).get("id"))
            else:
                rec["status"] = "failed"
                rec["create_errors"] = create_resp.get("errors")
                rec["verify_errors"] = verify_resp.get("errors")

            results.append(rec)
            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000)

    summary = {
        "started_at": started_at,
        "finished_at": datetime.utcnow().isoformat() + "Z",
        "csv": str(csv_path),
        "shops": shop_keys,
        "mode": args.mode,
        "dry_run": args.dry_run,
        "counts": {
            "total": len(results),
            "created_or_exists_after_create": sum(1 for r in results if r.get("status") == "created_or_exists_after_create"),
            "skipped_existing": sum(1 for r in results if r.get("status") == "skipped_existing"),
            "invalid": sum(1 for r in results if r.get("status") == "invalid"),
            "failed": sum(1 for r in results if r.get("status") == "failed"),
            "dry_run": sum(1 for r in results if r.get("status") == "dry_run"),
        },
        "items": results,
    }

    report_path = args.report_json
    if not report_path:
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        report_path = str(csv_path.parent / f"mercari_api_upload_report_{stamp}.json")
    Path(report_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"report_json": report_path, "counts": summary["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
