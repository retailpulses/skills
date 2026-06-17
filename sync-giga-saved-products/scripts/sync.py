#!/usr/bin/env python3
"""Hardened GigaB2B → Baserow 886994 saved-products sync with critical-field gating.

Usage:
    python3 sync.py              # dry-run: fetch + validate + preview, no writes
    python3 sync.py --apply      # confirm and write (BLOCKED if any critical field missing)
    python3 sync.py --apply --force  # write what you can, skip gated SKUs
    python3 sync.py --days 60    # custom lookback (default 30)
    python3 sync.py --preview 20 # more SKUs in preview (default 10)
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
from urllib.parse import urlencode

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
BASEROW_API = ENV.get("BASEROW_BASE_URL", "https://api.baserow.io").rstrip("/") + "/api"
BASEROW_TOKEN = ENV.get("BASEROW_TOKEN")
GIGA_BASE = ENV.get("GIGA_API_BASE_URL", "https://openapi.gigab2b.com")
GIGA_CID = ENV.get("GIGA_CLIENT_ID")
GIGA_CS = ENV.get("GIGA_CLIENT_SECRET")
TABLE_ID = "886994"

assert all([BASEROW_TOKEN, GIGA_CID, GIGA_CS]), "Missing credentials in .env"

BR_HEADERS = {"Authorization": f"Token {BASEROW_TOKEN}", "User-Agent": "Retailpulses-Sync/2.0"}

# Critical fields that MUST be present before writing
CRITICAL_FIELDS = [
    "Unit Price",
    "Unit Fulfillment Fee (Drop Shipping)",
    "Image URLs JSON",
    "Product Features",
]

# ─── Baserow helpers ──────────────────────────────────────────────

def br_get(path, params=None):
    url = f"{BASEROW_API}{path}"
    if params:
        url += "?" + urlencode(params)
    with urlopen(Request(url, headers=BR_HEADERS)) as r:
        return json.loads(r.read())

def br_post(path, body):
    h = dict(BR_HEADERS)
    h["Content-Type"] = "application/json"
    with urlopen(Request(f"{BASEROW_API}{path}", data=json.dumps(body).encode(), headers=h)) as r:
        return json.loads(r.read())

def fetch_existing_item_codes():
    codes = set()
    page = 1
    while True:
        data = br_get(f"/database/rows/table/{TABLE_ID}/",
                      {"user_field_names": "true", "size": 200, "page": page})
        for row in data.get("results", []):
            ic = row.get("item code", "").strip()
            if ic:
                codes.add(ic)
        n = len(data["results"])
        print(f"  Baserow page {page}: {n} rows, codes: {len(codes)}")
        if not data.get("next"):
            break
        page += 1
    return codes

# ─── GigaB2B helpers ──────────────────────────────────────────────

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
    """Call detailInfo/v1 for a list of SKUs; returns dict sku→data."""
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
    """Call price/v1 for a list of SKUs; returns dict sku→data."""
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

# ─── Field mapping ────────────────────────────────────────────────

def build_row_data(sku, detail, price):
    """Build a complete Baserow row from detailInfo + price data. Returns dict."""
    row = {"item code": sku}

    # ── From detailInfo ──
    if detail:
        # Image URLs JSON (critical)
        imgs = detail.get("imageUrls") or []
        if imgs:
            row["Image URLs JSON"] = json.dumps(imgs, ensure_ascii=False)

        # Product Features (critical) — prefer characteristics, fallback to attributes
        chars = detail.get("characteristics") or []
        attrs = detail.get("attributes") or {}
        if chars:
            row["Product Features"] = "\n".join(chars)
        elif attrs:
            row["Product Features"] = "\n".join(f"{k}: {v}" for k, v in attrs.items())

        # Bonus fields
        if detail.get("productName"):
            row["Product Name"] = detail["productName"]
        if detail.get("mainImageUrl"):
            row["Product Main Image"] = detail["mainImageUrl"]
        if detail.get("mainColor"):
            row["Main Color"] = detail["mainColor"]
        if detail.get("mainMaterial"):
            row["Main Material"] = detail["mainMaterial"]
            row["Main_Material"] = detail["mainMaterial"]
        if detail.get("category"):
            row["Internal_Cat_Name"] = detail["category"]
        if detail.get("placeOfOrigin"):
            row["Country_of_Origin_JA"] = detail["placeOfOrigin"]
        if detail.get("mpn"):
            row["SPU2（メーカー型番）"] = detail["mpn"]

        # Package dimensions
        if detail.get("weightKg") is not None:
            row["Package Size-Weight (kg)"] = str(detail["weightKg"])
        if detail.get("lengthCm") is not None:
            row["Package Size-Length (cm)"] = str(detail["lengthCm"])
        if detail.get("widthCm") is not None:
            row["Package Size-Width (cm)"] = str(detail["widthCm"])
        if detail.get("heightCm") is not None:
            row["Package Size-Height (cm)"] = str(detail["heightCm"])
        total_cm = sum(float(detail.get(k, 0) or 0) for k in ("lengthCm", "widthCm", "heightCm"))
        if total_cm > 0:
            row["Package Size-Total (cm)"] = str(round(total_cm, 2))
        if detail.get("weight"):
            row["Product Weight (kg)"] = str(detail["weight"])

        # Product Specification
        spec_parts = []
        for k, label in [("weightKg", "Weight (kg)"), ("lengthCm", "Length (cm)"),
                          ("widthCm", "Width (cm)"), ("heightCm", "Height (cm)")]:
            v = detail.get(k)
            if v is not None:
                spec_parts.append(f"{label}: {v}")
        for k, label in [("assembledWeight", "Assembled Weight"),
                          ("assembledLength", "Assembled Length"),
                          ("assembledWidth", "Assembled Width"),
                          ("assembledHeight", "Assembled Height")]:
            v = detail.get(k)
            if v is not None:
                spec_parts.append(f"{label}: {v}")
        if detail.get("mainMaterial"):
            spec_parts.append(f"Main Material: {detail['mainMaterial']}")
        if detail.get("mainColor"):
            spec_parts.append(f"Main Color: {detail['mainColor']}")
        if spec_parts:
            row["Product Specification"] = "\n".join(spec_parts)

    # ── From price ──
    if price:
        if price.get("price") is not None:
            row["Unit Price"] = str(price["price"])
        if price.get("shippingFee") is not None:
            row["Unit Fulfillment Fee (Drop Shipping)"] = str(price["shippingFee"])
        if price.get("exclusivePrice") is not None:
            row["Exclusive Price"] = str(price["exclusivePrice"])

        seller = price.get("sellerInfo") or {}
        if seller.get("sellerCode"):
            row["Store Code"] = seller["sellerCode"]
        if seller.get("sellerStore"):
            row["Store Name"] = seller["sellerStore"]
        if seller.get("sellerType"):
            row["Seller Type"] = seller["sellerType"]
        if seller.get("gigaIndex"):
            row["GIGA Index"] = seller["gigaIndex"]

    return row


def validate_critical(sku, row_data):
    """Check if all critical fields are present. Returns (pass: bool, missing: list)."""
    missing = []
    for field in CRITICAL_FIELDS:
        if not row_data.get(field):
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

    # Step 1: Fetch existing Baserow item codes
    print("=== STEP 1: Fetching existing Baserow item codes ===")
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
        row = build_row_data(sku, detail, price)
        # Add saved-products data if not overridden
        if not row.get("Product Name") and unique.get(sku, {}).get("productName"):
            row["Product Name"] = unique[sku]["productName"]
        if not row.get("Added Time") and unique.get(sku, {}).get("addedTime"):
            row["Added Time"] = unique[sku]["addedTime"]

        ok, missing = validate_critical(sku, row)
        rows[sku] = row
        if ok:
            pass_skus.append(sku)
        else:
            failures.append({"sku": sku, "missing": missing})

    print(f"  PASS: {len(pass_skus)} SKUs (all 4 critical fields present)")
    if failures:
        print(f"  FAIL: {len(failures)} SKUs (missing critical fields):")
        for f in failures:
            name = rows[f["sku"]].get("Product Name", "")[:60]
            print(f"    {f['sku']}: missing {', '.join(f['missing'])}")
            print(f"      {name}")
    print()

    result = {
        "window_days": lookback_days,
        "window_start": start_str,
        "window_end": end_str,
        "saved_total": len(saved),
        "giga_unique": len(unique),
        "existing_count": len(existing_codes),
        "skipped": len(unique) - len(new_skus),
        "new_count": len(new_skus),
        "pass_count": len(pass_skus),
        "fail_count": len(failures),
        "new_skus": new_skus,
        "pass_skus": pass_skus,
        "rows": rows,
        "failures": failures,
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
    print(f"  Already in Baserow:     {scope['skipped']}")
    print(f"  New SKUs:               {len(new)}")
    print(f"  PASS validation:        {scope['pass_count']}")
    if failures:
        print(f"  FAIL validation:        {scope['fail_count']} (would be skipped)")
    print()

    if scope["pass_count"]:
        print(f"  {'SKU':<22s} | {'Unit Price':>10s} | {'ShipFee':>7s} | {'Img':>4s} | {'Feat':>4s} | Product Name")
        print(f"  {'-' * 22}-+-{'-' * 10}-+-{'-' * 7}-+-{'-' * 4}-+-{'-' * 4}-+-{'-' * 40}")
        for sku in scope["pass_skus"][:preview_count]:
            r = rows[sku]
            up = r.get("Unit Price", "-")
            sf = r.get("Unit Fulfillment Fee (Drop Shipping)", "-")
            im = f"{len(json.loads(r['Image URLs JSON']))}im" if r.get("Image URLs JSON") else "✗"
            pf = "✓" if r.get("Product Features") else "✗"
            name = r.get("Product Name", "")[:38]
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

    print(f"\nAbout to create {len(pass_skus)} new rows in Baserow table {TABLE_ID}.")
    resp = input("Proceed? [y/N] ").strip().lower()
    if resp not in ("y", "yes"):
        print("Aborted.")
        return

    # Get schema for field presence checks
    field_names = [f["name"] for f in br_get(f"/database/fields/table/{TABLE_ID}/")]

    print(f"\n=== Writing {len(pass_skus)} rows ===")
    start_t = time_mod.time()
    created = 0
    errors = []
    for sku in pass_skus:
        row = rows[sku]
        # Only send fields that exist in Baserow schema
        clean = {k: v for k, v in row.items() if k in field_names}
        try:
            br_post(f"/database/rows/table/{TABLE_ID}/?user_field_names=true", clean)
            created += 1
            if created % 25 == 0:
                print(f"  {created}/{len(pass_skus)}...")
        except HTTPError as e:
            body = e.read().decode()[:200] if e.fp else ""
            errors.append(f"{sku}: HTTP {e.code} - {body}")
            print(f"  ERROR {sku}: HTTP {e.code}")

    elapsed = time_mod.time() - start_t
    print(f"\n  Created: {created}, Errors: {len(errors)}, Time: {elapsed:.1f}s")

    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)

    print("\n=== SYNC COMPLETE ===")
    print(f"  Saved-products records:  {scope['saved_total']}")
    print(f"  Already in Baserow:      {scope['skipped']}")
    print(f"  New rows created:        {created}")
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
            try: preview_count = int(sys.argv[i + 1])
            except ValueError: pass
        elif arg == "--days" and i < len(sys.argv) - 1:
            try: lookback_days = int(sys.argv[i + 1])
            except ValueError: pass

    scope = compute_scope(lookback_days)

    if apply:
        do_apply(scope, force)
    else:
        do_preview(scope, preview_count)


if __name__ == "__main__":
    main()
