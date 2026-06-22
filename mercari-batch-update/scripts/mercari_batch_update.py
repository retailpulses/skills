#!/usr/bin/env python3
"""
Mercari Batch Update — batch update existing Mercari Shop listings from CSV.

Supports: price, title, description, category ID (individually or combined).
Safety: validate -> dry-run -> apply workflow with price pre-check and rate limiting.

Based on mercari_bulk_product_updater.py with added categoryId support.
"""

import os
import csv
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

# --- Optional imports (graceful degradation for skill portability) ---
try:
    from baserow_client.client import BaserowClient
except ImportError:
    BaserowClient = None

try:
    from csv_common.encoding import detect_encoding, load_dotenv
except ImportError:
    def detect_encoding(path):
        # Minimal fallback: try utf-8, then cp932
        for enc in ["utf-8", "utf-8-sig", "cp932", "shift_jis"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    f.read(1024)
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "utf-8"

    def load_dotenv():
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = val


try:
    from mercari_common.graphql import MercariGraphQLClient
except ImportError:
    MercariGraphQLClient = None

try:
    from mercari_common.shop_config import SHOP_ID_TO_NAME, SHOP_NAMES
except ImportError:
    SHOP_ID_TO_NAME = {}
    SHOP_NAMES = {"shop1": "Shop1", "shop2": "Shop2", "shop3": "Shop3", "shop4": "Shop4"}

try:
    from mercari_common.tokens import resolve_shop_tokens
except ImportError:
    def resolve_shop_tokens(shops):
        """Fallback: read tokens directly from environment."""
        tokens = {}
        for shop in shops:
            key = f"MERCARI_{shop.upper()}_TOKEN"
            val = os.environ.get(key, "")
            if val:
                tokens[shop] = val
        return tokens


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASEROW_TABLE_ID = "938452"

MUTATION = """
mutation updateProducts($inputs: [UpdateProductInput!]!) {
  updateProducts(inputs: $inputs) {
    products {
      id
      name
      description
      price
    }
  }
}
"""

QUERY_PRODUCT = """
query productVariant($skuCode: ID!) {
  productVariant(by: { skuCode: $skuCode }) {
    skuCode
    product {
      id
      price
      status
    }
  }
}
"""

# Canonical column map: CSV header -> internal key.
# Supports English, Japanese, and common aliases.
COLUMN_MAP = {
    # Product identity
    "Listing ID": "product_id",
    "Item Code (SKU)": "sku_code",
    "SKU": "sku_code",
    "sku_code": "sku_code",
    "product_id": "product_id",
    "商品ID": "product_id",
    "商品管理番号": "sku_code",
    # Price
    "Current Prod Price": "old_price",
    "NEW Prod Price": "new_price",
    "old_price": "old_price",
    "new_price": "new_price",
    "販売価格": "new_price",
    "現在価格": "old_price",
    # Title
    "商品名": "new_title",
    "proposed_title": "new_title",
    "new_title": "new_title",
    "タイトル": "new_title",
    # Description
    "商品説明": "new_description",
    "new_description": "new_description",
    "説明": "new_description",
    # Category ID (NEW)
    "category_id": "category_id",
    "カテゴリID": "category_id",
    "Mercari category ID": "category_id",
    # Shop
    "shop_name": "shop_name",
    "Shop": "shop_name",
    "shop_id": "shop_id",
    "Shop ID": "shop_id",
    "ショップ": "shop_name",
}


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class MercariBatchUpdater:
    """Handles Mercari GraphQL product queries and batch updates."""

    def __init__(self):
        # Resolve tokens for all 4 shops
        if resolve_shop_tokens is not None:
            self.tokens = resolve_shop_tokens(["shop1", "shop2", "shop3", "shop4"])
        else:
            self.tokens = {}
        missing = [k for k in ["shop1", "shop2", "shop3", "shop4"] if k not in self.tokens]
        if missing:
            raise RuntimeError(
                f"Missing API tokens for: {', '.join(missing)}. "
                f"Set MERCARI_SHOP1_TOKEN .. MERCARI_SHOP4_TOKEN environment variables."
            )

    def _client(self, shop_name: str):
        """Get a MercariGraphQLClient for the given shop."""
        token = self.tokens.get(shop_name.lower())
        if not token:
            raise RuntimeError(f"Missing token for {shop_name}")
        if MercariGraphQLClient is None:
            raise RuntimeError("mercari_common.graphql is not available on PYTHONPATH")
        return MercariGraphQLClient(token=token)

    def fetch_live_products(self, shop_name, sku_codes):
        """Fetch live product data for a list of SKU codes.

        Returns (result_dict, error_string). result_dict maps product_id -> {price, name, status, skuCode}.
        """
        client = self._client(shop_name)
        result = {}
        for sku in sku_codes:
            resp = client.execute(QUERY_PRODUCT, {"skuCode": sku})
            if "errors" in resp:
                msg = resp["errors"][0].get("message", "Unknown")
                if "not found" in msg.lower() or "productVariant" in msg.lower():
                    continue
                return None, msg

            pv = (resp.get("data") or {}).get("productVariant")
            if pv and pv.get("product"):
                prod = pv["product"]
                pid = prod["id"]
                result[pid] = {
                    "price": prod.get("price"),
                    "name": prod.get("name", ""),
                    "status": prod.get("status"),
                    "skuCode": pv.get("skuCode", ""),
                }
            time.sleep(0.2)
        return result, None

    def update_batch(self, shop_name, batch_inputs):
        """Send a batch of up to 20 updates.

        Returns (success_map, error_map, global_error_string).
        """
        client = self._client(shop_name)
        resp = client.execute(MUTATION, {"inputs": batch_inputs})

        success_map = {}
        error_map = {}

        updated_products = (resp.get("data") or {}).get("updateProducts") or {}
        products_list = updated_products.get("products") or []
        for p in products_list:
            if isinstance(p, dict) and "id" in p:
                success_map[p["id"]] = p

        if "errors" in resp:
            for e in resp["errors"]:
                msg = e.get("message", "Unknown Error")
                path = e.get("path", [])
                if len(path) >= 3 and path[0] == "updateProducts" and isinstance(path[2], int):
                    idx = path[2]
                    if idx < len(batch_inputs):
                        pid = batch_inputs[idx]["id"]
                        error_map[pid] = msg
                else:
                    return success_map, error_map, msg

        return success_map, error_map, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_bool(val):
    if val is None:
        return False
    return str(val).strip().lower() in ("true", "1", "yes")


def _parse_price(val, label="price"):
    """Parse a price value; raises ValueError on invalid input."""
    if val is None or str(val).strip() == "":
        raise ValueError(f"{label} is empty")
    cleaned = str(val).replace(",", "").strip()
    try:
        price = int(float(cleaned))
    except (ValueError, TypeError):
        raise ValueError(f"{label} is not a valid number: {val}")
    if price <= 0:
        raise ValueError(f"{label} must be positive, got {price}")
    return price


def _parse_category_id(val, label="category_id"):
    """Parse a Mercari category ID; raises ValueError on invalid input."""
    if val is None or str(val).strip() == "":
        raise ValueError(f"{label} is empty")
    cleaned = str(val).strip()
    try:
        cat_id = int(cleaned)
    except (ValueError, TypeError):
        raise ValueError(f"{label} is not a valid integer: {val}")
    if cat_id <= 0:
        raise ValueError(f"{label} must be a positive integer, got {cat_id}")
    return cat_id


def _normalize_row(row):
    """Map CSV columns to internal keys using COLUMN_MAP."""
    out = {}
    for csv_col, internal in COLUMN_MAP.items():
        if csv_col in row:
            out[internal] = row[csv_col].strip()

    # Resolve shop name from shop_id if needed
    if not out.get("shop_name") and out.get("shop_id"):
        shop_key = SHOP_ID_TO_NAME.get(out["shop_id"])
        out["shop_name"] = SHOP_NAMES.get(shop_key, "") if shop_key else ""

    return out


def sync_to_baserow(results, update_types):
    """Sync SUCCESS results back to Baserow table 938452.

    Only marks price-update fields when price was actually changed.
    Falls back to product_id-only lookup when sku_code is missing.
    """
    if BaserowClient is None:
        print("\n[Baserow Sync] Skipped: baserow_client not available on PYTHONPATH")
        return

    token = os.environ.get("BASEROW_TOKEN") or os.environ.get("RP_BASEROW_TOKEN", "")
    if not token:
        print("\n[Baserow Sync] Skipped: BASEROW_TOKEN not found in environment")
        return

    client = BaserowClient(token)
    success_rows = [r for r in results if r.get("status") == "SUCCESS"]
    if not success_rows:
        print("\n[Baserow Sync] No successful updates to sync.")
        return

    print(f"\n[Baserow Sync] Syncing {len(success_rows)} successful updates to Baserow...")

    # Build lookup from all rows in table
    all_rows = client.fetch_all_rows(int(BASEROW_TABLE_ID))
    lookup = {}
    for brow in all_rows:
        pid = brow.get("Listing ID", "")
        sku = brow.get("Item Code (SKU)", "")
        # Index by (product_id, sku_code) and also by product_id alone as fallback
        lookup[(pid, sku)] = brow["id"]
        if pid and pid not in lookup:
            lookup[pid] = brow["id"]

    now_date = datetime.now().strftime("%Y-%m-%d")
    updated_count = 0

    for r in success_rows:
        pid = r["product_id"]
        sku = r.get("sku_code", "")
        # Try (pid, sku) lookup first, then fall back to pid-only
        row_id = lookup.get((pid, sku)) or lookup.get(pid)
        if not row_id:
            continue

        patch = {"If updated": True}
        # Only mark Price Changed At when price was actually in the update
        if "price" in update_types:
            patch["Price Changed At"] = now_date
        client.patch_row(int(BASEROW_TABLE_ID), row_id, patch)
        updated_count += 1
        time.sleep(0.2)

    print(f"[Baserow Sync] Successfully updated {updated_count} rows in Baserow.")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Mercari Shops Batch Updater (price / title / description / category ID)"
    )
    parser.add_argument("--csv", required=True, help="Input CSV path")
    parser.add_argument("--dry-run", action="store_true", help="Preview updates without executing mutations")
    parser.add_argument("--confirm", action="store_true",
                        help="Acknowledge: bypass dry-run requirement and execute live mutations")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between batch requests (default: 0.5)")
    parser.add_argument("--shop", default=None, help="Force a single shop (skip per-row shop detection from CSV)")
    args = parser.parse_args()

    # --- Load .env if present ---
    load_dotenv()

    # --- Read CSV ---
    encoding = detect_encoding(args.csv)
    with open(args.csv, mode="r", encoding=encoding) as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        raw_rows = list(reader)

    print(f"CSV headers: {headers}")
    print(f"Encoding: {encoding} | Rows: {len(raw_rows)}")

    # --- Detect update types from column mapping ---
    internal_cols = set()
    for csv_col in headers:
        if csv_col in COLUMN_MAP:
            internal_cols.add(COLUMN_MAP[csv_col])
        else:
            print(f"  Unmapped column: '{csv_col}'")

    has_price_update = "old_price" in internal_cols and "new_price" in internal_cols
    has_title_update = "new_title" in internal_cols
    has_desc_update = "new_description" in internal_cols
    has_category_update = "category_id" in internal_cols
    has_sku = "sku_code" in internal_cols
    has_shop_from_csv = "shop_name" in internal_cols or "shop_id" in internal_cols

    update_types = []
    if has_price_update:
        update_types.append("price")
    if has_title_update:
        update_types.append("title")
    if has_desc_update:
        update_types.append("description")
    if has_category_update:
        update_types.append("category")

    print(f"Mapped internal columns: {internal_cols}")

    if not update_types:
        print(
            "ERROR: CSV must contain at least one update column. Supported:\n"
            "  price:  old_price + new_price (or 現在価格 + 販売価格)\n"
            "  title:  new_title (or 商品名)\n"
            "  desc:   new_description (or 商品説明)\n"
            "  category: category_id (or カテゴリID)"
        )
        return

    # --- Safety gates ---
    if has_price_update and not has_sku:
        print(
            "WARNING: Price update columns detected but no sku_code column.\n"
            "  Without sku_code, live price pre-check is IMPOSSIBLE — you may overwrite\n"
            "  TimeSale prices or externally changed prices with no verification.\n"
            "  Add an 'Item Code (SKU)' column to enable pre-check, or pass --confirm\n"
            "  to acknowledge this risk."
        )
        if not args.confirm:
            print("  Aborting. Re-run with --confirm to bypass this check.")
            return
        print("  --confirm passed: proceeding without price pre-check.\n")

    if not args.dry_run and not args.confirm:
        print(
            "ERROR: Live execution requires --confirm.\n"
            "  Always dry-run first:  --csv <file> --dry-run\n"
            "  Then apply:            --csv <file> --confirm\n"
            "  Or combine dry-run + confirm for a preview-then-apply pipeline."
        )
        return

    # Resolve shop: --shop flag overrides, otherwise detect from CSV rows
    shop_name = args.shop
    if not shop_name and has_shop_from_csv:
        # Detect shop from CSV — use the first non-empty shop_name found
        shop_names_seen = set()
        for row in raw_rows:
            norm = _normalize_row(row)
            sn = norm.get("shop_name", "").strip()
            if sn:
                shop_names_seen.add(sn)
        if len(shop_names_seen) == 1:
            shop_name = shop_names_seen.pop()
        elif len(shop_names_seen) > 1:
            print(
                f"ERROR: CSV contains rows for multiple shops: {sorted(shop_names_seen)}.\n"
                f"  Multi-shop batch updates are not supported. Split into separate CSVs per shop\n"
                f"  or use --shop to force a single shop."
            )
            return
    if not shop_name:
        shop_name = "Shop3"  # default

    print(f"Detected updates: {', '.join(update_types)}  |  Shop: {shop_name}")

    # --- Validate & normalize rows ---
    rows = []
    skipped = 0
    errors = []
    seen_ids = set()

    for idx, row in enumerate(raw_rows, 1):
        norm = _normalize_row(row)

        if not norm.get("product_id"):
            skipped += 1
            continue

        # Price validation
        if has_price_update:
            missing = [k for k in ("old_price", "new_price") if not norm.get(k)]
            if missing:
                errors.append(f"Row {idx}: Missing price column(s): {missing}")
                skipped += 1
                continue
            try:
                norm["old_price"] = str(_parse_price(norm["old_price"], f"Row {idx} old_price"))
                norm["new_price"] = str(_parse_price(norm["new_price"], f"Row {idx} new_price"))
            except ValueError as e:
                errors.append(f"Row {idx}: {e}")
                skipped += 1
                continue

        # Category ID validation (NEW)
        if has_category_update and norm.get("category_id"):
            try:
                norm["category_id"] = str(_parse_category_id(norm["category_id"], f"Row {idx} category_id"))
            except ValueError as e:
                errors.append(f"Row {idx}: {e}")
                skipped += 1
                continue

        # Dedup
        pid = norm["product_id"]
        if pid in seen_ids:
            print(f"  SKIP Row {idx}: Duplicate product_id={pid}")
            skipped += 1
            continue
        seen_ids.add(pid)

        rows.append(norm)

    if errors:
        print(f"\nValidation errors:")
        for e in errors:
            print(f"  - {e}")

    if not rows:
        print(f"[{datetime.now().isoformat()}] No valid rows to process ({skipped} skipped).")
        return

    print(f"[{datetime.now().isoformat()}] Starting update for {len(rows)} products "
          f"({', '.join(update_types)}) ({skipped} skipped).")

    if args.dry_run:
        print("!!! DRY RUN MODE — no mutations will be executed !!!")

    # --- Initialize updater ---
    updater = MercariBatchUpdater()

    # --- Process in batches ---
    results = []
    needs_pre_check = has_price_update and has_sku

    for i in range(0, len(rows), 20):
        batch_rows = rows[i: i + 20]
        batch_num = i // 20 + 1

        batch_inputs = []
        safe_rows = []

        if needs_pre_check:
            sku_codes = [r["sku_code"] for r in batch_rows]
            print(f"  Checking live products for batch {batch_num}...")
            live_products, p_err = updater.fetch_live_products(shop_name, sku_codes)

            if p_err:
                print(f"  Skipping batch due to pre-check error: {p_err}")
                for row in batch_rows:
                    results.append({**row, "status": "FAILED_PRECHECK", "error": p_err})
                continue

            for row in batch_rows:
                pid = row["product_id"]
                live = live_products.get(pid)

                if not live:
                    print(f"  SKIP {row['sku_code']}: Product not found in live data.")
                    results.append({**row, "status": "SKIPPED_NOT_FOUND"})
                    continue

                current_price = live.get("price")
                expected_price = int(float(row["old_price"]))

                if current_price != expected_price:
                    print(f"  SKIP {row['sku_code']}: Price mismatch "
                          f"(live={current_price} != expected={expected_price}). Possibly on TimeSale.")
                    results.append({**row, "status": "SKIPPED_PRICE_MISMATCH", "live_price": current_price})
                    continue

                live_sku = live.get("skuCode", "")
                if live_sku and live_sku != row["sku_code"]:
                    print(f"  SKIP {row['sku_code']}: SKU mismatch "
                          f"(live={live_sku}, csv={row['sku_code']}). WRONG PRODUCT!")
                    results.append({**row, "status": "SKIPPED_SKU_MISMATCH", "live_sku": live_sku})
                    continue

                # Build mutation input — include ALL update fields
                inp = {"id": pid, "price": int(float(row["new_price"]))}
                if has_title_update and row.get("new_title"):
                    title = row["new_title"]
                    if len(title) > 127:
                        title = title[:127]
                    inp["name"] = title
                if has_desc_update and row.get("new_description"):
                    inp["description"] = row["new_description"]
                if has_category_update and row.get("category_id"):
                    inp["categoryId"] = int(row["category_id"])
                batch_inputs.append(inp)
                safe_rows.append(row)
        else:
            # No price pre-check — build inputs directly
            for row in batch_rows:
                pid = row["product_id"]
                inp = {"id": pid}

                if has_title_update and row.get("new_title"):
                    title = row["new_title"]
                    if len(title) > 127:
                        title = title[:127]
                    inp["name"] = title
                if has_desc_update and row.get("new_description"):
                    inp["description"] = row["new_description"]
                if has_price_update and row.get("new_price"):
                    inp["price"] = int(float(row["new_price"]))
                if has_category_update and row.get("category_id"):
                    inp["categoryId"] = int(row["category_id"])

                if len(inp) > 1:  # more than just id
                    batch_inputs.append(inp)
                    safe_rows.append(row)
                else:
                    results.append({**row, "status": "SKIPPED_NO_CONTENT"})

        if not batch_inputs:
            continue

        # --- Execute or dry-run ---
        if args.dry_run:
            for row in safe_rows:
                parts = [f"ID={row['product_id']}"]
                if has_title_update and row.get("new_title"):
                    t = row["new_title"]
                    parts.append(f"title='{t[:50]}{'...' if len(t) > 50 else ''}'")
                if has_desc_update and row.get("new_description"):
                    parts.append(f"description=<{len(row['new_description'])} chars>")
                if has_price_update and row.get("old_price") and row.get("new_price"):
                    parts.append(f"price: {row.get('old_price', '?')} -> {row.get('new_price', '?')}")
                if has_category_update and row.get("category_id"):
                    parts.append(f"category_id={row['category_id']}")
                print(f"  [DRY-RUN] {' | '.join(parts)}")
            results.extend([
                {**r, "status": "DRY_RUN", "timestamp": datetime.now().isoformat()}
                for r in safe_rows
            ])
        else:
            print(f"  Sending {len(batch_inputs)} updates (batch {batch_num})...")
            success_map, error_map, global_err = updater.update_batch(shop_name, batch_inputs)

            if global_err:
                print(f"  Batch Error: {global_err}")
                for row in safe_rows:
                    results.append({
                        **row,
                        "status": "FAILED_BATCH",
                        "error": global_err,
                        "timestamp": datetime.now().isoformat(),
                    })
            else:
                for row in safe_rows:
                    pid = row["product_id"]
                    if pid in success_map:
                        results.append({
                            **row,
                            "status": "SUCCESS",
                            "timestamp": datetime.now().isoformat(),
                        })
                    elif pid in error_map:
                        print(f"  Product Error {pid}: {error_map[pid]}")
                        results.append({
                            **row,
                            "status": "FAILED_PRODUCT",
                            "error": error_map[pid],
                            "timestamp": datetime.now().isoformat(),
                        })
                    else:
                        results.append({
                            **row,
                            "status": "MISSING_IN_RESPONSE",
                            "timestamp": datetime.now().isoformat(),
                        })

            time.sleep(args.interval)

    # --- Save results CSV ---
    all_keys = []
    seen_keys_writer = set()
    for r in results:
        for k in r.keys():
            if k not in seen_keys_writer:
                all_keys.append(k)
                seen_keys_writer.add(k)

    suffix = "dryrun" if args.dry_run else "results"
    output_path = args.csv.replace(".csv", f"_{suffix}_{int(time.time())}.csv")
    with open(output_path, mode="w", encoding="utf-8", newline="") as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=all_keys)
            writer.writeheader()
            writer.writerows(results)
            print(f"\nExecution log saved to: {output_path}")

    # --- Summary ---
    status_counts = {}
    for r in results:
        s = r.get("status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1
    print(f"\nSummary ({'DRY RUN' if args.dry_run else 'LIVE'}):")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    # --- Baserow sync (live mode only, any update type) ---
    if not args.dry_run:
        sync_to_baserow(results, update_types)


if __name__ == "__main__":
    main()
