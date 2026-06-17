#!/usr/bin/env python3
"""Backfill Baserow 886994: PATCH missing fields using GigaB2B detailInfo + price.

Uses Baserow PATCH batch endpoint for efficient multi-row updates.

Usage:
    python3 backfill.py              # dry-run: show what would be patched
    python3 backfill.py --apply --yes # apply patches (no interactive prompt)
"""

import json, os, sys, hmac, hashlib, base64, time as time_mod, random, string
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SKILL_DIR, ".env")) as f:
    env = dict(line.strip().split('=', 1) for line in f if '=' in line and not line.startswith('#') and line.strip())

CID = env['GIGA_CLIENT_ID']; CS = env['GIGA_CLIENT_SECRET']
TOKEN = env['BASEROW_TOKEN']
BR_API = env.get('BASEROW_BASE_URL', 'https://api.baserow.io').rstrip('/') + '/api'
TABLE = '886994'
BATCH_SIZE = 100

BR = {"Authorization": f"Token {TOKEN}", "User-Agent": "Retailpulses-Backfill/3.0"}

# ─── Helpers ──────────────────────────────────────────────────────

def giga_post(api_path, body):
    ts = str(int(time_mod.time() * 1000)); nonce = ''.join(random.choices(string.digits, k=10))
    msg = f'{CID}&{api_path}&{ts}&{nonce}'; key = f'{CID}&{CS}&{nonce}'
    sig = base64.b64encode(hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest().encode()).decode()
    r = urlopen(Request(f'https://openapi.gigab2b.com{api_path}',
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'client-id': CID, 'timestamp': ts, 'nonce': nonce, 'sign': sig}))
    return json.loads(r.read())

def br_get(path, params=None):
    url = f'{BR_API}{path}' + ('?' + urlencode(params) if params else '')
    with urlopen(Request(url, headers=BR)) as r:
        return json.loads(r.read())

def br_patch_batch(items):
    h = dict(BR); h['Content-Type'] = 'application/json'
    data = json.dumps({"items": items}).encode()
    req = Request(f'{BR_API}/database/rows/table/{TABLE}/batch/?user_field_names=true',
                  data=data, headers=h, method='PATCH')
    with urlopen(req) as r:
        return json.loads(r.read())

def br_delete(row_id):
    h = dict(BR)
    req = Request(f'{BR_API}/database/rows/table/{TABLE}/{row_id}/', headers=h, method='DELETE')
    with urlopen(req) as r:
        return r.status

# ─── GigaB2B batch fetches ────────────────────────────────────────

def batch_fetch(api_path, skus):
    result = {}
    for i in range(0, len(skus), BATCH_SIZE):
        batch = skus[i:i + BATCH_SIZE]
        resp = giga_post(api_path, {'skus': batch})
        items = resp.get('data', []) if isinstance(resp.get('data'), list) else []
        for item in items:
            result[item.get('sku', '')] = item
        print(f'  batch {i // BATCH_SIZE + 1}: {len(batch)} -> {len(items)}')
    return result

# ─── Patch builder ────────────────────────────────────────────────

def build_patch(detail, price, writable_names):
    p = {}
    if detail:
        imgs = detail.get('imageUrls') or []
        if imgs: p['Image URLs JSON'] = json.dumps(imgs, ensure_ascii=False)
        chars = detail.get('characteristics') or []
        attrs = detail.get('attributes') or {}
        if chars: p['Product Features'] = '\n'.join(chars)
        elif attrs: p['Product Features'] = '\n'.join(f'{k}: {v}' for k, v in attrs.items())
        if detail.get('productName'): p['Product Name'] = detail['productName']
        if detail.get('mainImageUrl'): p['Product Main Image'] = detail['mainImageUrl']
        if detail.get('mainColor'): p['Main Color'] = detail['mainColor']
        if detail.get('mainMaterial'):
            p['Main Material'] = detail['mainMaterial']
            p['Main_Material'] = detail['mainMaterial']
        if detail.get('category'): p['Internal_Cat_Name'] = detail['category']
        if detail.get('placeOfOrigin'): p['Country_of_Origin_JA'] = detail['placeOfOrigin']
        for k, label in [('weightKg', 'Package Size-Weight (kg)'),
                         ('lengthCm', 'Package Size-Length (cm)'),
                         ('widthCm', 'Package Size-Width (cm)'),
                         ('heightCm', 'Package Size-Height (cm)')]:
            if detail.get(k) is not None: p[label] = str(detail[k])
        if detail.get('weight'): p['Product Weight (kg)'] = str(detail['weight'])
        spec_parts = []
        for k, lab in [('weightKg', 'Weight (kg)'), ('lengthCm', 'Length (cm)'),
                       ('widthCm', 'Width (cm)'), ('heightCm', 'Height (cm)')]:
            if detail.get(k) is not None: spec_parts.append(f'{lab}: {detail[k]}')
        for k, lab in [('assembledWeight', 'Assembled Weight'), ('assembledLength', 'Assembled Length'),
                       ('assembledWidth', 'Assembled Width'), ('assembledHeight', 'Assembled Height')]:
            if detail.get(k) is not None: spec_parts.append(f'{lab}: {detail[k]}')
        if detail.get('mainMaterial'): spec_parts.append(f'Main Material: {detail["mainMaterial"]}')
        if detail.get('mainColor'): spec_parts.append(f'Main Color: {detail["mainColor"]}')
        if spec_parts: p['Product Specification'] = '\n'.join(spec_parts)
    if price:
        if price.get('price') is not None: p['Unit Price'] = str(price['price'])
        if price.get('shippingFee') is not None: p['Unit Fulfillment Fee (Drop Shipping)'] = str(price['shippingFee'])
        if price.get('exclusivePrice') is not None: p['Exclusive Price'] = str(price['exclusivePrice'])
        s = price.get('sellerInfo') or {}
        if s.get('sellerCode'): p['Store Code'] = s['sellerCode']
        if s.get('sellerStore'): p['Store Name'] = s['sellerStore']
        if s.get('sellerType'): p['Seller Type'] = s['sellerType']
        if s.get('gigaIndex'): p['GIGA Index'] = s['gigaIndex']
    # Filter to only writable Baserow fields
    return {k: v for k, v in p.items() if k in writable_names}

# ─── Baserow SKU -> row_id scan ───────────────────────────────────

def build_sku_id_map():
    print("  Scanning all Baserow rows for SKU -> ID map...")
    sku_to_id = {}
    page = 1
    while True:
        data = br_get(f'/database/rows/table/{TABLE}/',
                      {"user_field_names": "true", "size": 200, "page": page})
        for row in data.get("results", []):
            sku = (row.get("item code") or "").strip()
            if sku:
                sku_to_id[sku] = row["id"]
        n = len(data["results"])
        print(f"  Page {page}: {n} rows, map size: {len(sku_to_id)}")
        if not data.get("next"):
            break
        page += 1
    return sku_to_id

# ─── Get writable Baserow field names ─────────────────────────────

def get_writable_names():
    fields = br_get(f'/database/fields/table/{TABLE}/')
    readonly = {'formula', 'autonumber', 'created_on', 'updated_on', 'last_modified_by', 'created_by'}
    return {f['name'] for f in fields if f.get('type') not in readonly}

# ─── Main ─────────────────────────────────────────────────────────

def main():
    apply = '--apply' in sys.argv
    start_t = time_mod.time()

    # 1. Get SKUs from saved-products
    print("=== STEP 1: GigaB2B saved-products (30 days) ===")
    resp = giga_post('/b2b-overseas-api/v1/buyer/product/skus/v1', {
        'queryTimeType': 2, 'startTime': '2026-05-16 00:00:00', 'endTime': '2026-06-15 23:59:59',
        'page': 1, 'page_size': 100, 'sort': 4})
    skus = sorted(set(r['sku'] for r in resp['data']['records']))
    print(f"  {len(skus)} unique SKUs")

    # 2. Build SKU -> row_id map (from Baserow full scan)
    print(f"\n=== STEP 2: Building SKU -> row_id map ===")
    sku_to_id = build_sku_id_map()
    missed = [s for s in skus if s not in sku_to_id]
    if missed:
        print(f"  WARNING: {len(missed)} SKUs not found in Baserow: {missed[:5]}...")
        skus = [s for s in skus if s in sku_to_id]
    print(f"  {len(skus)} SKUs have row IDs")

    # 3. Fetch detailInfo + price
    print(f"\n=== STEP 3: detailInfo + price ({len(skus)} SKUs) ===")
    details = batch_fetch('/b2b-overseas-api/v1/buyer/product/detailInfo/v1', skus)
    prices = batch_fetch('/b2b-overseas-api/v1/buyer/product/price/v1', skus)
    print(f"  detailInfo: {len(details)}, price: {len(prices)}")

    # 4. Get writable fields + build patches
    print("\n=== STEP 4: Building patches (writable fields only) ===")
    writable = get_writable_names()
    print(f"  Writable fields: {len(writable)}, read-only filtered: {133 - len(writable)}")

    patches = {}
    stats = {'Image URLs JSON': 0, 'Product Features': 0, 'Unit Price': 0,
             'Unit Fulfillment Fee (Drop Shipping)': 0, 'Product Specification': 0,
             'Store Code': 0, 'Product Main Image': 0, 'Main Color': 0,
             'Main Material': 0, 'Exclusive Price': 0}
    for sku in skus:
        patch = build_patch(details.get(sku), prices.get(sku), writable)
        if patch:
            patches[sku] = patch
            for k in patch:
                if k in stats:
                    stats[k] += 1

    for k, v in stats.items():
        print(f"  {k}: {v}/{len(skus)}")

    # Show sample
    print(f"\n  Sample patches:")
    for sku in sorted(patches)[:3]:
        p = patches[sku]
        print(f"    {sku} (row {sku_to_id[sku]}): {len(p)} fields — {sorted(p)[:5]}...")

    if not apply:
        elapsed = time_mod.time() - start_t
        print(f"\n=== DRY-RUN ({elapsed:.0f}s): Would batch-PATCH {len(patches)} rows. Use --apply --yes. ===")
        return

    # 5. PATCH via batch endpoint
    print(f"\n=== STEP 5: Batch-PATCHing {len(patches)} rows ===")
    batch_items = [{"id": sku_to_id[sku], **patch} for sku, patch in sorted(patches.items())]

    ok = 0; errs = 0
    for i in range(0, len(batch_items), BATCH_SIZE):
        chunk = batch_items[i:i + BATCH_SIZE]
        try:
            resp = br_patch_batch(chunk)
            updated = len(resp.get('items', []))
            ok += updated
            print(f"  Chunk {i // BATCH_SIZE + 1}: {len(chunk)} sent, {updated} updated, total: {ok}")
        except HTTPError as e:
            body = e.read().decode()[:300] if e.fp else str(e)
            print(f"  Chunk {i // BATCH_SIZE + 1} ERROR: {e.code} {body}")
            errs += len(chunk)

    elapsed = time_mod.time() - start_t

    # 6. Clean up test row
    print(f"\n=== STEP 6: Clean up test row 22324 ===")
    try:
        br_delete(22324)
        print("  Deleted test row 22324")
    except Exception as e:
        print(f"  Could not delete row 22324: {e}")

    print(f"\n=== DONE ({elapsed:.0f}s) ===")
    print(f"  Rows patched: {ok}")
    print(f"  Errors:       {errs}")
    print(f"  Fields/row:   ~{len(next(iter(patches.values()), {}))} fields")


if __name__ == '__main__':
    main()
