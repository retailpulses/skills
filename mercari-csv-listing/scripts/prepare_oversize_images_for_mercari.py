#!/usr/bin/env python3
"""Preprocess oversize product images (>10MB) for Mercari CSV generation.

Resize to 1500x1500 progressive JPEG, upload to Cloudflare R2, and update
Baserow URLs. Uses requests.Session for connection reuse and
ThreadPoolExecutor for parallel image download/resize/upload.

Performance: ~560s→~55s (10 workers, session reuse).
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from io import BytesIO
from typing import Dict, List, Optional, Set, Tuple

from PIL import Image, ImageOps
from supabase_db import SupabaseDB, resolve_credentials

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
IMAGE_URL_RE = re.compile(r"https?://[^,\s]+")
EXCLUDE_MAIN_RE = re.compile(r"^Product Images \(exclude main\)(\d+)$")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)


@dataclass
class ImageRef:
    field_name: str
    slot: int
    url: str
    row_id: int
    item_code: str
    source_type: str  # single | multi | json_array
    multi_urls: Optional[List[str]] = None
    multi_index: Optional[int] = None
    json_array_urls: Optional[List[str]] = None  # full array for source_type=json_array


@dataclass
class ProcessResult:
    row_id: int
    item_code: str
    slot: int
    field_name: str
    old_url: str
    new_url: Optional[str] = None
    original_bytes: Optional[int] = None
    resized_bytes: Optional[int] = None
    r2_key: Optional[str] = None
    error: Optional[str] = None


def load_dotenv(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def normalize_bucket_name(value: str) -> str:
    bucket = value.strip().lower().replace(" ", "-")
    bucket = re.sub(r"[^a-z0-9.-]", "-", bucket)
    bucket = re.sub(r"-+", "-", bucket).strip("-.")
    return bucket


def validate_public_base_url(base_url: str) -> None:
    if ".r2.cloudflarestorage.com" in base_url:
        raise ValueError(
            "--r2-public-base-url cannot be a cloudflarestorage API endpoint. "
            "Use a public custom domain or the bucket's r2.dev public URL."
        )


def ensure_bucket_exists(bucket: str, wrangler_config: Optional[str], dry_run: bool) -> None:
    cmd = ["wrangler", "r2", "bucket", "create", bucket]
    if wrangler_config:
        cmd.extend(["--config", wrangler_config])
    if dry_run:
        return
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0 and "already" not in combined.lower() and "exists" not in combined.lower():
        raise RuntimeError(
            f"Failed to create/check R2 bucket: {' '.join(shlex.quote(x) for x in cmd)}\n{combined}"
        )


def parse_item_codes_arg(path_or_csv: Optional[str]) -> Optional[Set[str]]:
    if not path_or_csv:
        return None
    if os.path.isfile(path_or_csv):
        codes = set()
        with open(path_or_csv, "r", encoding="utf-8") as f:
            for line in f:
                code = line.strip()
                if code:
                    codes.add(code)
        return codes
    return {x.strip() for x in path_or_csv.split(",") if x.strip()}


def fetch_rows_for_prepare(db: SupabaseDB, item_codes_filter: Optional[Set[str]]) -> List[dict]:
    """Fetch product rows from Supabase compat view for image preprocessing."""
    rows: List[dict] = []
    if item_codes_filter:
        result = db.fetch_by_item_codes(list(item_codes_filter))
        rows = list(result.values())
    else:
        # Fetch all — paginated via compat view
        # For full-table scans, fetch in batches by reading all item codes first
        # This avoids the Baserow full-table-scan pattern
        sys.stderr.write("WARN: Full-table scan without --item-codes not yet implemented for Supabase.\n")
        sys.stderr.write("      Use --item-codes to filter.\n")
        return []
    return rows


# ── R2 upload via wrangler ───────────────────────────────────────────

def upload_via_wrangler(
    local_file: str,
    bucket: str,
    key: str,
    wrangler_config: Optional[str],
    dry_run: bool,
) -> None:
    cmd = ["wrangler", "r2", "object", "put", f"{bucket}/{key}", "--file", local_file, "--remote"]
    if wrangler_config:
        cmd.extend(["--config", wrangler_config])
    if dry_run:
        return
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Failed to upload object to R2:\n"
            + " ".join(shlex.quote(x) for x in cmd)
            + "\n"
            + (proc.stdout or "")
            + "\n"
            + (proc.stderr or "")
        )


def build_public_url(base_url: str, key: str) -> str:
    return f"{base_url.rstrip('/')}/{urllib.parse.quote(key)}"


# ── Image field discovery ────────────────────────────────────────────

def parse_urls_from_value(value) -> Tuple[List[str], str]:
    if value is None:
        return [], "single"
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return [], "single"
        matches = IMAGE_URL_RE.findall(s)
        if len(matches) <= 1:
            return ([matches[0]] if matches else []), "single"
        return matches, "multi"
    if isinstance(value, list):
        urls: List[str] = []
        for item in value:
            if isinstance(item, dict):
                u = str(item.get("url") or "").strip()
                if u:
                    urls.append(u)
            elif isinstance(item, str):
                u = item.strip()
                if u:
                    urls.append(u)
        return urls, "multi"
    return [], "single"


def discover_image_fields(row: dict) -> Tuple[Optional[str], List[str], Optional[str]]:
    main = "Product Main Image" if "Product Main Image" in row else None
    exclude: List[Tuple[int, str]] = []
    additional = "Additional Images" if "Additional Images" in row else None
    for key in row.keys():
        m = EXCLUDE_MAIN_RE.match(key)
        if m:
            exclude.append((int(m.group(1)), key))
    exclude.sort(key=lambda x: x[0])
    return main, [k for _, k in exclude], additional


def collect_all_image_refs(rows: List[dict], item_code_field: str, image_field: str = "Image URLs JSON") -> List[ImageRef]:
    """Collect all image refs from all rows into a flat list for parallel processing.

    Primary source: *image_field* (JSON array of URL strings).
    Fallback: legacy individual image fields.
    """
    refs: List[ImageRef] = []
    for row in rows:
        item_code = str(row.get(item_code_field) or "").strip()
        row_id = row.get("id")
        if not item_code or row_id is None:
            continue

        json_raw = row.get(image_field)
        if json_raw:
            try:
                json_urls = json.loads(json_raw) if isinstance(json_raw, str) else json_raw
                if isinstance(json_urls, list) and json_urls:
                    for idx, u in enumerate(json_urls):
                        u = str(u).strip()
                        if u and u.startswith("http"):
                            refs.append(ImageRef(
                                field_name=image_field, slot=idx + 1, url=u,
                                row_id=row_id, item_code=item_code,
                                source_type="json_array",
                                json_array_urls=json_urls, multi_index=idx,
                            ))
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: legacy individual image fields
        main, exclude_fields, additional = discover_image_fields(row)
        slot = 1

        single_fields: List[str] = []
        if main:
            single_fields.append(main)
        single_fields.extend(exclude_fields)

        for field in single_fields:
            urls, _stype = parse_urls_from_value(row.get(field))
            if not urls:
                continue
            refs.append(ImageRef(
                field_name=field, slot=slot, url=urls[0],
                row_id=row_id, item_code=item_code, source_type="single",
            ))
            slot += 1

        if additional:
            add_urls, _stype = parse_urls_from_value(row.get(additional))
            for idx, u in enumerate(add_urls):
                refs.append(ImageRef(
                    field_name=additional, slot=slot, url=u,
                    row_id=row_id, item_code=item_code, source_type="multi",
                    multi_urls=add_urls, multi_index=idx,
                ))
                slot += 1

    return refs


# ── Image processing ─────────────────────────────────────────────────

def should_skip_head_check(url: str, skip_hosts: Set[str]) -> bool:
    """Check if HEAD request should be skipped for this URL's host."""
    if not skip_hosts:
        return False
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return False
    return host in skip_hosts


def resize_to_progressive_jpeg(raw: bytes, max_side: int, quality: int) -> bytes:
    with Image.open(BytesIO(raw)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="JPEG", progressive=True, optimize=True, quality=quality)
        return out.getvalue()


def process_single_image(
    session: requests.Session,
    ref: ImageRef,
    max_bytes: int,
    max_side: int,
    jpeg_quality: int,
    r2_bucket: str,
    r2_prefix: str,
    r2_public_base_url: str,
    wrangler_config: Optional[str],
    dry_run: bool,
    skip_head_check: bool,
    head_check_skip_hosts: Set[str],
) -> ProcessResult:
    """Download, resize, and upload a single image. Returns a ProcessResult."""
    result = ProcessResult(
        row_id=ref.row_id,
        item_code=ref.item_code,
        slot=ref.slot,
        field_name=ref.field_name,
        old_url=ref.url,
    )

    try:
        # HEAD check (configurable)
        needs_download = True
        if not skip_head_check and not should_skip_head_check(ref.url, head_check_skip_hosts):
            try:
                head_resp = session.head(ref.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                cl = head_resp.headers.get("Content-Length")
                if cl and int(cl) <= max_bytes:
                    needs_download = False
            except requests.RequestException:
                needs_download = True  # HEAD failed, try download anyway

        if not needs_download:
            return result  # already small enough

        # Download
        original_bytes = _download_with_retry(session, ref.url)
        if len(original_bytes) <= max_bytes:
            return result  # under threshold after download

        # Resize
        resized_bytes = resize_to_progressive_jpeg(original_bytes, max_side, jpeg_quality)

        # Upload to R2
        key_base = f"{ref.item_code}_{ref.slot:02d}.jpg"
        key = (
            f"{r2_prefix.strip('/')}/{ref.item_code}/{key_base}"
            if r2_prefix.strip("/")
            else f"{ref.item_code}/{key_base}"
        )

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            tf.write(resized_bytes)
            tmp_path = tf.name

        try:
            upload_via_wrangler(
                local_file=tmp_path,
                bucket=r2_bucket,
                key=key,
                wrangler_config=wrangler_config,
                dry_run=dry_run,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        new_url = build_public_url(r2_public_base_url, key)
        result.new_url = new_url
        result.original_bytes = len(original_bytes)
        result.resized_bytes = len(resized_bytes)
        result.r2_key = key

    except Exception as exc:
        result.error = str(exc)

    return result


def _download_with_retry(session: requests.Session, url: str, timeout: int = 60) -> bytes:
    last_exc = None
    for attempt in range(4):
        try:
            resp = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


# ── Build field patches from results ─────────────────────────────────

def build_patch_for_field(ref: ImageRef, new_url: str, multi_state: Dict[str, List[str]], json_array_state: Dict[str, list]) -> dict:
    if ref.source_type == "single":
        return {ref.field_name: new_url}

    if ref.source_type == "json_array":
        if ref.json_array_urls is None or ref.multi_index is None:
            return {}
        arr = json_array_state.get(ref.field_name)
        if arr is None:
            arr = list(ref.json_array_urls)
            json_array_state[ref.field_name] = arr
        if ref.multi_index < len(arr):
            arr[ref.multi_index] = new_url
        return {ref.field_name: json.dumps(arr, ensure_ascii=False)}

    if ref.multi_urls is None or ref.multi_index is None:
        return {}
    urls = multi_state.get(ref.field_name)
    if urls is None:
        urls = list(ref.multi_urls)
        multi_state[ref.field_name] = urls
    urls[ref.multi_index] = new_url
    return {ref.field_name: ", ".join(urls)}


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Preprocess oversize product images (>10MB) for Mercari CSV generation: "
            "resize to 1500x1500 progressive JPEG, upload to Cloudflare R2, and update Baserow URLs. "
            "Uses parallel downloads via ThreadPoolExecutor for speed."
        )
    )
    parser.add_argument("--token", default=None)
    parser.add_argument("--table-id", type=int, default=886994)
    parser.add_argument("--image-field", default="Image URLs JSON",
                        help="Baserow field name containing image URLs (JSON array). Falls back to legacy fields if empty.")
    parser.add_argument("--item-code-field", default="Item Code")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--max-side", type=int, default=1500)
    parser.add_argument("--jpeg-quality", type=int, default=82)
    parser.add_argument("--r2-bucket", default="resize-product-images")
    parser.add_argument("--r2-prefix", default="")
    parser.add_argument("--r2-public-base-url", required=True)
    parser.add_argument("--wrangler-config", default=None)
    parser.add_argument(
        "--item-codes", default=None,
        help="Comma-separated item codes or path to newline-separated item-code file",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--workers", type=int, default=10,
        help="Number of parallel workers for image download/resize/upload (default: 10)",
    )
    parser.add_argument(
        "--skip-head-check", action="store_true",
        help="Skip HEAD pre-check; download every image and check size after. "
        "Avoids ~11k HEAD calls for large catalogs at the cost of downloading small images.",
    )
    parser.add_argument(
        "--head-check-skip-hosts", default="",
        help="Comma-separated hostnames to skip HEAD checks for (e.g. 'cdn.giga.com,img.shop.com')",
    )
    args = parser.parse_args()

    key = resolve_credentials(args.token)
    if not key:
        raise SystemExit(
            "Missing Supabase key. Pass --token or set SUPABASE_SERVICE_ROLE_KEY."
        )

    db = SupabaseDB()

    validate_public_base_url(args.r2_public_base_url)
    bucket = normalize_bucket_name(args.r2_bucket)
    item_codes_filter = parse_item_codes_arg(args.item_codes)
    head_check_skip_hosts = {h.strip() for h in args.head_check_skip_hosts.split(",") if h.strip()}

    ensure_bucket_exists(bucket=bucket, wrangler_config=args.wrangler_config, dry_run=args.dry_run)

    # ── Fetch rows from Supabase compat view ──────────────────────
    rows = fetch_rows_for_prepare(db, item_codes_filter)

    # Filter by item codes if provided (belt-and-suspenders)
    item_code_field = args.item_code_field  # "Item Code" or "item code"
    if item_codes_filter:
        rows = [r for r in rows if str(r.get(item_code_field) or "").strip() in item_codes_filter]

    # ── Collect all image refs ───────────────────────────────────
    all_refs = collect_all_image_refs(rows, args.item_code_field, args.image_field)
    if not all_refs:
        print(json.dumps({
            "bucket_effective": bucket,
            "table_id": args.table_id,
            "rows_total": len(rows),
            "rows_scanned": 0,
            "rows_with_updates": 0,
            "rows_updated": 0,
            "replaced_images": 0,
            "errors": 0,
            "dry_run": args.dry_run,
            "items": [],
        }, ensure_ascii=False, indent=2))
        return

    # ── Process images in parallel ───────────────────────────────
    report_items: List[dict] = []
    results: List[ProcessResult] = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                process_single_image,
                session=session,
                ref=ref,
                max_bytes=args.max_bytes,
                max_side=args.max_side,
                jpeg_quality=args.jpeg_quality,
                r2_bucket=bucket,
                r2_prefix=args.r2_prefix,
                r2_public_base_url=args.r2_public_base_url,
                wrangler_config=args.wrangler_config,
                dry_run=args.dry_run,
                skip_head_check=args.skip_head_check,
                head_check_skip_hosts=head_check_skip_hosts,
            ): ref
            for ref in all_refs
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    # ── Build patches grouped by item_code ──────────────────────────
    row_patches: Dict[str, Dict] = {}  # item_code → {field: value, ...}
    row_json_array_state: Dict[str, Dict[str, list]] = {}
    ref_by_result = {r.slot: r for r in all_refs}

    for result in results:
        item = {
            "item_code": result.item_code,
            "slot": result.slot,
            "field_name": result.field_name,
            "old_url": result.old_url,
        }
        if result.error:
            item["error"] = result.error
        elif result.new_url:
            item["new_url"] = result.new_url
            item["original_bytes"] = result.original_bytes
            item["resized_bytes"] = result.resized_bytes
            item["r2_key"] = result.r2_key

            # Build field patch for this item_code
            ic = result.item_code
            if ic not in row_patches:
                row_patches[ic] = {}

            # For Supabase, only image_urls_json needs updating
            matching_ref = None
            for ref in all_refs:
                if ref.row_id == result.row_id and ref.slot == result.slot:
                    matching_ref = ref
                    break

            if matching_ref and matching_ref.source_type == "json_array":
                if ic not in row_json_array_state:
                    row_json_array_state[ic] = {}
                field = "image_urls_json"
                arr = row_json_array_state[ic].get(field)
                if arr is None:
                    arr = list(matching_ref.json_array_urls) if matching_ref.json_array_urls else []
                    row_json_array_state[ic][field] = arr
                if matching_ref.multi_index is not None and matching_ref.multi_index < len(arr):
                    arr[matching_ref.multi_index] = result.new_url
                row_patches[ic]["image_urls_json"] = arr

        report_items.append(item)

    # ── Write to Supabase ──────────────────────────────────────────
    patch_list = []
    for item_code, patch_data in row_patches.items():
        p = {"item_code": item_code}
        p.update(patch_data)
        patch_list.append(p)

    updated_rows = 0
    if patch_list and not args.dry_run:
        # Batch update image_urls_json via SupabaseDB
        for p in patch_list:
            if db.update_image_urls_json(p["item_code"], p.get("image_urls_json", [])):
                updated_rows += 1

    scanned = len({r.row_id for r in results if not r.error}) or len(row_patches)

    output = {
        "bucket_requested": args.r2_bucket,
        "bucket_effective": bucket,
        "table_id": args.table_id,
        "rows_total": len(rows),
        "rows_scanned": scanned,
        "rows_with_updates": len(updates),
        "rows_updated": 0 if args.dry_run else updated_rows,
        "replaced_images": len([x for x in report_items if x.get("new_url")]),
        "errors": len([x for x in report_items if x.get("error")]),
        "dry_run": args.dry_run,
        "workers": args.workers,
        "skip_head_check": args.skip_head_check,
        "head_check_skip_hosts": sorted(head_check_skip_hosts) if head_check_skip_hosts else [],
        "items": report_items,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
