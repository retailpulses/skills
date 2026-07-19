#!/usr/bin/env python3
"""GigaB2B → Supabase product sync (replaces Baserow 886994 path).

Usage:
    python3 sync_to_supabase.py              # dry-run: fetch + validate + preview, no writes
    python3 sync_to_supabase.py --apply      # confirm and write (BLOCKED if any critical field missing)
    python3 sync_to_supabase.py --apply --force  # write what you can, skip gated SKUs
    python3 sync_to_supabase.py --days 60    # custom lookback (default 30)
    python3 sync_to_supabase.py --preview 20 # more SKUs in preview (default 10)

Environment:
    SUPABASE_URL          — https://<project-ref>.supabase.co
    SUPABASE_SERVICE_ROLE_KEY — service_role key for writes
    GIGA_CLIENT_ID, GIGA_CLIENT_SECRET, GIGA_API_BASE_URL

Requires: supabase-py (pip install supabase)
"""

import json
import os
import sys
import hmac
import hashlib
import base64
import time as time_mod
import random
import string
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase-py not installed. Run: pip install supabase")
    sys.exit(1)

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SKILL_DIR, ".env")
CACHE_FILE = os.path.join(SKILL_DIR, ".sync_cache.json")
BATCH_SIZE = 100

# ─── Config ───────────────────────────────────────────────────────

def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

ENV = load_env()
SUPABASE_URL = ENV.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = ENV.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
GIGA_BASE = ENV.get("GIGA_API_BASE_URL", "https://openapi.gigab2b.com")
GIGA_CID = ENV.get("GIGA_CLIENT_ID", os.environ.get("GIGA_CLIENT_ID", ""))
GIGA_CS = ENV.get("GIGA_CLIENT_SECRET", os.environ.get("GIGA_CLIENT_SECRET", ""))

assert all([SUPABASE_URL, SUPABASE_KEY, GIGA_CID, GIGA_CS]), \
    "Missing credentials: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GIGA_CLIENT_ID, GIGA_CLIENT_SECRET"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Critical fields that MUST be present before writing (Supabase column names)
CRITICAL_FIELDS = [
    "source_unit_price",       # Unit Price → product_commercials
    "fulfillment_fee",         # Unit Fulfillment Fee → product_commercials
    "image_urls_json",         # Image URLs JSON → product_variants
    "product_features",        # Product Features → product_variants
]

# ─── Supabase helpers ─────────────────────────────────────────────

def fetch_existing_item_codes():
    """Paginate product_variants to get all existing item codes."""
    codes = set()
    page_size = 1000
    start = 0
    while True:
        resp = (supabase.table("product_variants")
                .select("item_code", count="exact")
                .range(start, start + page_size - 1)
                .execute())
        batch = resp.data or []
        if not batch:
            break
        for row in batch:
            ic = (row.get("item_code") or "").strip()
            if ic:
                codes.add(ic)
        n = len(batch)
        print(f"  product_variants [{start}:{start + n}]: {n} rows, total codes: {len(codes)}")
        if n < page_size:
            break
        start += page_size
    return codes


def supabase_upsert_variant(item_code, variant_data):
    """Insert or update a row in product_variants by item_code. Returns variant_id."""
    existing = (supabase.table("product_variants")
                .select("id")
                .eq("item_code", item_code)
                .execute())
    if existing.data:
        variant_id = existing.data[0]["id"]
        supabase.table("product_variants").update(variant_data).eq("id", variant_id).execute()
        return variant_id, "updated"
    else:
        # Insert — need sku + item_code at minimum
        if "sku" not in variant_data:
            variant_data["sku"] = item_code
        resp = supabase.table("product_variants").insert(variant_data).execute()
        return resp.data[0]["id"], "created"


def supabase_upsert_commercial(variant_id, commercial_data):
    """Insert or update a row in product_commercials by variant_id."""
    existing = (supabase.table("product_commercials")
                .select("variant_id")
                .eq("variant_id", variant_id)
                .execute())
    commercial_data["variant_id"] = variant_id
    if existing.data:
        supabase.table("product_commercials").update(commercial_data).eq("variant_id", variant_id).execute()
        return "updated"
    else:
        supabase.table("product_commercials").insert(commercial_data).execute()
        return "created"

# ─── GigaB2B helpers (identical to sync.py) ──────────────────────

def giga_sign(api_path, timestamp, nonce):
    msg = f"{GIGA_CID}&{api_path}&{timestamp}&{nonce}"
    key = f"{GIGA_CID}&{GIGA_CS}&{nonce}"
    sig = hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return base64.b64encode(sig.encode()).decode()

def giga_post(api_path, body):
    ts = str(int(time_mod.time() * 1000))
    nonce = "".join(random.choices(string.digits, k=10))
    sign = giga_sign(api_path, ts, nonce)
    data = json.dumps(body).encode("utf-8")
    req = Request(f"{GIGA_BASE}{api_path}", data=data, headers={
        "Content-Type": "application/json", "client-id": GIGA_CID,
        "timestamp": ts, "nonce": nonce, "sign": sign,
    })
    with urlopen(req) as r:
        return json.loads(r.read())

def fetch_saved_products(start_str, end_str):
    api_path = "/b2b-overseas-api/v1/buyer/product/skus/v1"
    records = []
    page = 1
    while True:
        body = {"queryTimeType": 2, "startTime": start_str, "endTime": end_str,
                "page": page, "page_size": 100, "sort": 4}
        resp = giga_post(api_path, body)
        if not resp.get("success"):
            print(f"  GigaB2B error: {resp.get('msg')} - {resp.get('subMsg')}")
            break
        data = resp.get("data", {})
        pr = data.get("records", [])
        if not pr:
            break
        records.extend(pr)
        pi = data.get("pageInfo", {})
        total_pages = pi.get("totalPage", 1)
        print(f"  Saved-products page {page}: {len(pr)} records (totalNum={pi.get('totalNum')})")
        if page >= total_pages:
            break
        page += 1
    return records

def batch_detail_info(skus):
    api_path = "/b2b-overseas-api/v1/buyer/product/detailInfo/v1"
    result = {}
    for i in range(0, len(skus), BATCH_SIZE):
        batch = skus[i:i + BATCH_SIZE]
        resp = giga_post(api_path, {"skus": batch})
        items = resp.get("data", []) if isinstance(resp.get("data"), list) else []
        for item in items:
            result[item.get("sku", "")] = item
        print(f"  detailInfo batch {i // BATCH_SIZE + 1}: {len(batch)} → {len(items)} results")
    return result

def batch_price(skus):
    api_path = "/b2b-overseas-api/v1/buyer/product/price/v1"
    result = {}
    for i in range(0, len(skus), BATCH_SIZE):
        batch = skus[i:i + BATCH_SIZE]
        resp = giga_post(api_path, {"skus": batch})
        items = resp.get("data", []) if isinstance(resp.get("data"), list) else []
        for item in items:
            result[item.get("sku", "")] = item
        print(f"  price batch {i // BATCH_SIZE + 1}: {len(batch)} → {len(items)} results")
    return result

# ─── Field mapping (Baserow → Supabase) ──────────────────────────

def build_variant_payload(sku, detail, price):
    """Build the product_variants portion of the row. Returns dict."""
    v = {"item_code": sku, "sku": sku}

    if detail:
        # Content
        if detail.get("productName"):
            v["product_name"] = detail["productName"]
        if detail.get("description"):
            v["marketing_description"] = detail["description"]
        if detail.get("mainImageUrl"):
            v["product_main_image"] = detail["mainImageUrl"]
        if detail.get("firstArrivalDate"):
            v["first_arrival_date"] = detail["firstArrivalDate"]

        # Images (critical)
        imgs = detail.get("imageUrls") or []
        if imgs:
            v["image_urls_json"] = imgs  # JSONB — supabase-py will encode

        # Product Features (critical) — characteristics as bullet lines
        chars = detail.get("characteristics") or []
        attrs = detail.get("attributes") or {}
        if chars:
            v["product_features"] = "\n".join(chars)
        elif attrs:
            v["product_features"] = "\n".join(f"{k}: {v}" for k, v in attrs.items())

        # Color / Material
        if detail.get("mainColor"):
            v["main_color"] = detail["mainColor"]
        if detail.get("mainMaterial"):
            v["material"] = detail["mainMaterial"]

        # Category
        if detail.get("category"):
            v["internal_cat_name"] = detail["category"]
        if detail.get("categoryCode") is not None:
            v["internal_cat_id"] = str(detail["categoryCode"])

        def _is_numeric(val):
            """GigaB2B returns 'Not Applicable' for missing numeric fields."""
            if val is None:
                return False
            if isinstance(val, (int, float)):
                return True
            if isinstance(val, str) and val.strip().lower() in ("not applicable", "n/a", "na", ""):
                return False
            try:
                float(str(val))
                return True
            except (ValueError, TypeError):
                return False

        # Package dimensions
        if _is_numeric(detail.get("widthCm")):
            v["package_width_cm"] = detail["widthCm"]
        if _is_numeric(detail.get("lengthCm")):
            v["package_length_cm"] = detail["lengthCm"]
        if _is_numeric(detail.get("heightCm")):
            v["package_height_cm"] = detail["heightCm"]
        if _is_numeric(detail.get("weightKg")):
            v["package_weight_kg"] = detail["weightKg"]

        # Assembled dimensions / weight
        if _is_numeric(detail.get("assembledWidth")):
            v["assembled_width_cm"] = detail["assembledWidth"]
        if _is_numeric(detail.get("assembledLength")):
            v["assembled_length_cm"] = detail["assembledLength"]
        if _is_numeric(detail.get("assembledHeight")):
            v["assembled_height_cm"] = detail["assembledHeight"]
        if _is_numeric(detail.get("assembledWeight")):
            v["product_weight_kg"] = detail["assembledWeight"]
        elif _is_numeric(detail.get("weight")):
            v["product_weight_kg"] = detail["weight"]

        # Product Specification
        spec_parts = []
        for k, label in [("weightKg", "Weight (kg)"), ("lengthCm", "Length (cm)"),
                          ("widthCm", "Width (cm)"), ("heightCm", "Height (cm)")]:
            val = detail.get(k)
            if val is not None:
                spec_parts.append(f"{label}: {val}")
        for k, label in [("assembledWeight", "Assembled Weight"),
                          ("assembledLength", "Assembled Length"),
                          ("assembledWidth", "Assembled Width"),
                          ("assembledHeight", "Assembled Height")]:
            val = detail.get(k)
            if val is not None:
                spec_parts.append(f"{label}: {val}")
        if detail.get("mainMaterial"):
            spec_parts.append(f"Main Material: {detail['mainMaterial']}")
        if detail.get("mainColor"):
            spec_parts.append(f"Main Color: {detail['mainColor']}")
        if spec_parts:
            v["product_specification"] = "\n".join(spec_parts)

        # Combo flag
        if detail.get("comboFlag") is not None:
            v["combo_product"] = bool(detail["comboFlag"])

        # User manual
        files = detail.get("fileUrls") or []
        if files:
            v["user_manual_url"] = files[0]

        # Raw payload for traceability
        v["raw_payload"] = detail

    return v


def build_commercial_payload(sku, detail, price, inv=None):
    """Build the product_commercials portion of the row. Returns dict."""
    c = {}

    if price:
        # Pricing
        if price.get("price") is not None:
            c["source_unit_price"] = price["price"]
        if price.get("discountedPrice") is not None:
            c["discounted_unit_price"] = price["discountedPrice"]
        if price.get("exclusivePrice") is not None:
            c["baseline_price"] = price["exclusivePrice"]
        if price.get("shippingFee") is not None:
            c["fulfillment_fee"] = price["shippingFee"]
        if price.get("mapPrice") is not None:
            c["baseline_price"] = c.get("baseline_price") or price["mapPrice"]

        # NOTE: mercari_effective_price_incl_shipping and effective_cost_price
        # are auto-computed by PostgreSQL trigger trg_pricing on product_commercials.
        # The trigger implements the full Baserow formula:
        #   Mercari Effective Pricing (incl. shipping) =
        #     round((Mercari Effective Pricing (excl. shipping) + Unit Fulfillment Fee) / 50) * 50
        #   Mercari Effective Pricing (excl. shipping) =
        #     round((Effective TCOGS / 0.76 * Prcing COE * RMA Multiple - Unit Fulfillment Fee) / 50) * 50
        # where:
        #   Effective TCOGS = Effective Cost Price + Unit Fulfillment Fee
        #   Prcing COE = tiered by Unit Price (>12000→0.98, >8000→1.00, <3000→1.05, else→1.02)
        #   RMA Multiple = 1.0 (default), 1.06 (Moderate), 1.1 (High)

        # Discount / promotion
        if price.get("promotionFrom"):
            c["start_from"] = price["promotionFrom"]
        if price.get("promotionTo"):
            c["discount_promotion_end_time"] = price["promotionTo"]

        # Seller info
        seller = price.get("sellerInfo") or {}
        if seller:
            # Store metadata goes on product_variants via the variant payload
            pass

    if inv:
        if inv.get("sellerInventoryInfo", {}).get("sellerAvailableInventory") is not None:
            c["source_available_qty"] = inv["sellerInventoryInfo"]["sellerAvailableInventory"]
        if inv.get("buyerInventoryInfo", {}).get("totalBuyerAvailableInventory") is not None:
            c["owned_qty"] = inv["buyerInventoryInfo"]["totalBuyerAvailableInventory"]

        # Computed: inventory status
        qty = c.get("source_available_qty", 0) or 0
        more = detail.get("nextArrivalInventory", {}).get("nextArrivalQtyMax") if detail else None
        next_arrival = detail.get("nextArrivalInventory", {}).get("nextArrivalBegin") if detail else None
        if qty == 0:
            if more and next_arrival:
                c["inventory_status"] = "Incoming Stock"
            else:
                c["inventory_status"] = "Sold out"

    return c


def build_seller_payload(price):
    """Extract seller/store fields for product_variants. Returns dict or None."""
    if not price:
        return None
    seller = price.get("sellerInfo") or {}
    if not seller:
        return None
    sp = {}
    if seller.get("sellerCode"):
        sp["store_code"] = seller["sellerCode"]
    if seller.get("sellerStore"):
        sp["store_name"] = seller["sellerStore"]
    if seller.get("sellerType"):
        sp["seller_type"] = seller["sellerType"]
    if seller.get("gigaIndex"):
        sp["giga_index"] = seller["gigaIndex"]
    return sp if sp else None


def build_row_data(sku, detail, price, inv=None):
    """Build complete Supabase row from Giga API responses.
    Returns (variant_payload, commercial_payload) tuple.
    """
    v = build_variant_payload(sku, detail, price)
    sp = build_seller_payload(price)
    if sp:
        v.update(sp)
    c = build_commercial_payload(sku, detail, price, inv)
    return v, c


def validate_critical(sku, variant_data, commercial_data):
    """Check if all critical fields are present. Returns (pass: bool, missing: list)."""
    combined = {}
    combined.update(variant_data)
    combined.update(commercial_data)
    missing = []
    for field in CRITICAL_FIELDS:
        val = combined.get(field)
        if val is None or (isinstance(val, (list, str)) and len(val) == 0):
            missing.append(field)
    return len(missing) == 0, missing


# ─── Caching ──────────────────────────────────────────────────────

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return None

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Main ─────────────────────────────────────────────────────────

def compute_scope(lookback_days):
    cached = load_cache()
    if cached and cached.get("window_days") == lookback_days:
        print("(Using cached data. Delete .sync_cache.json to re-fetch.)\n")
        return cached

    # Step 1: Fetch existing Supabase item codes
    print("=== STEP 1: Fetching existing product_variants item codes ===")
    existing_codes = fetch_existing_item_codes()
    print(f"  Total existing: {len(existing_codes)}\n")

    # Step 2: Fetch new SKUs from saved-products
    print(f"=== STEP 2: GigaB2B saved products (last {lookback_days} days) ===")
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=lookback_days)
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"  Window: {start_str} → {end_str}")
    saved = fetch_saved_products(start_str, end_str)
    print(f"  Total: {len(saved)}\n")

    # Step 3: Dedup → new SKUs
    print("=== STEP 3: Dedup vs existing ===")
    unique = {}
    for r in saved:
        sku = str(r.get("sku", "")).strip()
        if sku and sku not in unique:
            unique[sku] = {"productName": r.get("productName", ""), "addedTime": r.get("addedTime", "")}
    new_skus = sorted(set(unique) - existing_codes)
    print(f"  Unique from Giga: {len(unique)}, New: {len(new_skus)}, Already exist: {len(unique) - len(new_skus)}\n")

    if not new_skus:
        result = {"window_days": lookback_days, "window_start": start_str, "window_end": end_str,
                  "saved_total": len(saved), "giga_unique": len(unique), "existing_count": len(existing_codes),
                  "skipped": len(unique), "new_count": 0, "new_skus": [], "rows": {}, "failures": []}
        save_cache(result)
        return result

    # Step 4: Batch fetch detailInfo
    print(f"=== STEP 4: Batch-fetching detailInfo for {len(new_skus)} SKUs ===")
    details = batch_detail_info(new_skus)
    print(f"  Got details for {len(details)} SKUs\n")

    # Step 5: Batch fetch price
    print(f"=== STEP 5: Batch-fetching price for {len(new_skus)} SKUs ===")
    prices = batch_price(new_skus)
    print(f"  Got prices for {len(prices)} SKUs\n")

    # Step 6: Build rows + validate
    print("=== STEP 6: Building rows + validating critical fields ===")
    rows = {}
    pass_skus = []
    failures = []

    for sku in new_skus:
        detail = details.get(sku)
        price = prices.get(sku)
        variant, commercial = build_row_data(sku, detail, price)

        # Add saved-products fallback
        if not variant.get("product_name") and unique.get(sku, {}).get("productName"):
            variant["product_name"] = unique[sku]["productName"]

        ok, missing = validate_critical(sku, variant, commercial)
        rows[sku] = {"variant": variant, "commercial": commercial}
        if ok:
            pass_skus.append(sku)
        else:
            failures.append({"sku": sku, "missing": missing})

    print(f"  PASS: {len(pass_skus)} SKUs (all critical fields present)")
    if failures:
        print(f"  FAIL: {len(failures)} SKUs (missing critical fields):")
        for f in failures:
            name = rows[f["sku"]]["variant"].get("product_name", "")[:60]
            print(f"    {f['sku']}: missing {', '.join(f['missing'])}")
            print(f"      {name}")
    print()

    result = {
        "window_days": lookback_days, "window_start": start_str, "window_end": end_str,
        "saved_total": len(saved), "giga_unique": len(unique), "existing_count": len(existing_codes),
        "skipped": len(unique) - len(new_skus), "new_count": len(new_skus),
        "pass_count": len(pass_skus), "fail_count": len(failures),
        "new_skus": new_skus, "pass_skus": pass_skus, "rows": rows, "failures": failures,
    }
    save_cache(result)
    return result


def do_preview(scope, preview_count):
    new = scope["new_skus"]
    failures = scope["failures"]
    rows = scope["rows"]

    print()
    if not new:
        print("=== DRY-RUN: No new saved products to sync. ===")
        return

    print(f"=== DRY-RUN: {len(new)} new SKUs found ===")
    print(f"  Window: {scope['window_start']} → {scope['window_end']}")
    print(f"  Saved-products records: {scope['saved_total']}")
    print(f"  Already in Supabase:    {scope['skipped']}")
    print(f"  New SKUs:               {len(new)}")
    print(f"  PASS validation:        {scope['pass_count']}")
    if failures:
        print(f"  FAIL validation:        {scope['fail_count']} (would be skipped)")
    print()

    if scope["pass_count"]:
        print(f"  {'SKU':<22s} | {'UnitPrice':>10s} | {'ShipFee':>7s} | {'Img':>4s} | {'Feat':>4s} | Product Name")
        print(f"  {'-' * 22}-+-{'-' * 10}-+-{'-' * 7}-+-{'-' * 4}-+-{'-' * 4}-+-{'-' * 40}")
        for sku in scope["pass_skus"][:preview_count]:
            r = rows[sku]
            v = r["variant"]
            c = r["commercial"]
            up = str(c.get("source_unit_price", "")) or "-"
            sf = str(c.get("fulfillment_fee", "")) or "-"
            imgs = v.get("image_urls_json", [])
            im = f"{len(imgs)}im" if imgs else "✗"
            pf = "✓" if v.get("product_features") else "✗"
            name = (v.get("product_name") or "")[:38]
            print(f"  {sku:<22s} | {up:>10s} | {sf:>7s} | {im:>4s} | {pf:>4s} | {name}")
        if len(scope["pass_skus"]) > preview_count:
            print(f"  ... and {len(scope['pass_skus']) - preview_count} more (--preview N to show)")

    if failures:
        print(f"\n  FAILED validation ({len(failures)} SKUs):")
        for f in failures:
            print(f"    {f['sku']}: missing {', '.join(f['missing'])}")

    print()
    if failures:
        print("=== WARNING: Some SKUs failed critical field validation. ===")
        print(f"  Use --apply --force to write {scope['pass_count']} passing rows and skip {scope['fail_count']} failures.")
        print(f"  Or resolve the missing fields and re-run.")
    elif scope["pass_count"]:
        print(f"=== End of dry-run. Run with --apply to create {scope['pass_count']} rows. ===")
    else:
        print("=== End of dry-run. ===")


def do_apply(scope, force):
    pass_skus = scope["pass_skus"]
    rows = scope["rows"]
    failures = scope["failures"]

    if not pass_skus:
        print("No passing SKUs to write.")
        return

    if failures and not force:
        print(f"\nBLOCKED: {len(failures)} SKU(s) failed critical field validation.")
        for f in failures:
            print(f"  {f['sku']}: missing {', '.join(f['missing'])}")
        print(f"\n  Use --apply --force to write only {len(pass_skus)} passing rows and skip failures.")
        return

    if force and failures:
        print(f"\nForce mode: writing {len(pass_skus)} passing rows, skipping {len(failures)} failures.")

    print(f"\nAbout to upsert {len(pass_skus)} rows into Supabase product_variants + product_commercials.")
    resp = input("Proceed? [y/N] ").strip().lower()
    if resp not in ("y", "yes"):
        print("Aborted.")
        return

    print(f"\n=== Writing {len(pass_skus)} rows ===")
    start_t = time_mod.time()
    created_v = 0
    updated_v = 0
    created_c = 0
    updated_c = 0
    errors = []

    for sku in pass_skus:
        r = rows[sku]
        variant_data = r["variant"]
        commercial_data = r["commercial"]

        try:
            vid, v_action = supabase_upsert_variant(sku, variant_data)
            if v_action == "created":
                created_v += 1
            else:
                updated_v += 1

            c_action = supabase_upsert_commercial(vid, commercial_data)
            if c_action == "created":
                created_c += 1
            else:
                updated_c += 1

            if (created_v + updated_v) % 25 == 0:
                print(f"  {created_v + updated_v}/{len(pass_skus)}...")
        except Exception as e:
            errors.append(f"{sku}: {e}")
            print(f"  ERROR {sku}: {e}")

    elapsed = time_mod.time() - start_t
    print(f"\n  Variants:  {created_v} created, {updated_v} updated")
    print(f"  Commercials: {created_c} created, {updated_c} updated")
    print(f"  Errors: {len(errors)}, Time: {elapsed:.1f}s")

    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)

    print("\n=== SYNC COMPLETE ===")
    print(f"  Saved-products records:  {scope['saved_total']}")
    print(f"  Already in Supabase:     {scope['skipped']}")
    print(f"  New variants created:    {created_v}")
    if scope["fail_count"]:
        print(f"  Skipped (validation):    {scope['fail_count']}")
    if errors:
        print(f"  Errors:                  {len(errors)}")
        for e in errors:
            print(f"    {e}")


def main():
    apply = "--apply" in sys.argv
    force = "--force" in sys.argv
    preview_count = 10
    lookback_days = 30

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--preview" and i < len(sys.argv) - 1:
            try:
                preview_count = int(sys.argv[i + 1])
            except ValueError:
                pass
        elif arg == "--days" and i < len(sys.argv) - 1:
            try:
                lookback_days = int(sys.argv[i + 1])
            except ValueError:
                pass

    scope = compute_scope(lookback_days)

    if apply:
        do_apply(scope, force)
    else:
        do_preview(scope, preview_count)


if __name__ == "__main__":
    main()
