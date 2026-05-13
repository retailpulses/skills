#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageOps

BASEROW_API = "https://api.baserow.io/api"
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
    source_type: str  # single | multi
    multi_urls: Optional[List[str]] = None
    multi_index: Optional[int] = None


def http_json(req: urllib.request.Request, timeout: int = 60) -> dict:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_table_rows(token: str, table_id: int) -> List[dict]:
    rows: List[dict] = []
    page = 1
    headers = {"Authorization": f"Token {token}"}
    while True:
        url = (
            f"{BASEROW_API}/database/rows/table/{table_id}/"
            f"?user_field_names=true&size=200&page={page}"
        )
        req = urllib.request.Request(url, headers=headers)
        data = None
        for attempt in range(4):
            try:
                data = http_json(req, timeout=120)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
        if data is None:
            raise RuntimeError(f"Failed to fetch Baserow table page {page}")
        batch = data.get("results", [])
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 200:
            break
        page += 1
    return rows


def fetch_rows_by_item_codes(
    token: str,
    table_id: int,
    item_code_field: str,
    item_codes: set,
) -> List[dict]:
    headers = {"Authorization": f"Token {token}"}
    rows: List[dict] = []
    seen_ids = set()
    for code in sorted(item_codes):
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {
                    "user_field_names": "true",
                    "size": 200,
                    "page": page,
                    f"filter__{item_code_field}__equal": code,
                }
            )
            url = f"{BASEROW_API}/database/rows/table/{table_id}/?{query}"
            req = urllib.request.Request(url, headers=headers)
            data = None
            for attempt in range(4):
                try:
                    data = http_json(req, timeout=120)
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(1.5 * (attempt + 1))
            if data is None:
                raise RuntimeError(f"Failed to fetch Baserow filtered rows for item code {code}")
            batch = data.get("results", [])
            if not batch:
                break
            for row in batch:
                row_id = row.get("id")
                if row_id in seen_ids:
                    continue
                seen_ids.add(row_id)
                rows.append(row)
            if len(batch) < 200:
                break
            page += 1
    return rows


def patch_rows(token: str, table_id: int, items: List[dict]) -> List[dict]:
    if not items:
        return []
    url = f"{BASEROW_API}/database/rows/table/{table_id}/batch/?user_field_names=true"
    req = urllib.request.Request(
        url,
        data=json.dumps({"items": items}).encode(),
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    return http_json(req, timeout=120).get("items", [])


def normalize_bucket_name(value: str) -> str:
    # R2 bucket naming does not allow spaces; normalize user-friendly labels.
    bucket = value.strip().lower().replace(" ", "-")
    bucket = re.sub(r"[^a-z0-9.-]", "-", bucket)
    bucket = re.sub(r"-+", "-", bucket).strip("-.")
    return bucket


def ensure_bucket_exists(bucket: str, wrangler_config: Optional[str], dry_run: bool) -> None:
    cmd = ["wrangler", "r2", "bucket", "create", bucket]
    if wrangler_config:
        cmd.extend(["--config", wrangler_config])
    if dry_run:
        return
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # Accept both create success and already-existing states.
    if proc.returncode != 0 and "already" not in combined.lower() and "exists" not in combined.lower():
        raise RuntimeError(f"Failed to create/check R2 bucket: {' '.join(shlex.quote(x) for x in cmd)}\n{combined}")


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


def collect_image_refs(row: dict) -> List[ImageRef]:
    main, exclude_fields, additional = discover_image_fields(row)
    refs: List[ImageRef] = []
    slot = 1

    single_fields: List[str] = []
    if main:
        single_fields.append(main)
    single_fields.extend(exclude_fields)

    for field in single_fields:
        urls, stype = parse_urls_from_value(row.get(field))
        if not urls:
            continue
        refs.append(ImageRef(field_name=field, slot=slot, url=urls[0], source_type="single"))
        slot += 1

    if additional:
        add_urls, stype = parse_urls_from_value(row.get(additional))
        for idx, u in enumerate(add_urls):
            refs.append(
                ImageRef(
                    field_name=additional,
                    slot=slot,
                    url=u,
                    source_type="multi",
                    multi_urls=add_urls,
                    multi_index=idx,
                )
            )
            slot += 1

    return refs


def head_content_length(url: str, timeout: int = 20) -> Optional[int]:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cl = resp.headers.get("Content-Length")
            return int(cl) if cl else None
    except Exception:
        return None


def download_bytes(url: str, timeout: int = 60) -> bytes:
    last_error: Optional[Exception] = None
    for attempt in range(4):
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(1.5 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("download failed without exception")


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


def parse_item_codes_arg(path_or_csv: Optional[str]) -> Optional[set]:
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


def resolve_baserow_token(cli_token: Optional[str]) -> Optional[str]:
    if cli_token:
        return cli_token.strip()
    for key in ("BASEROW_TOKEN", "RP_BASEROW_TOKEN", "TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def validate_public_base_url(base_url: str) -> None:
    # This host is the S3 API endpoint, not a public object URL for third-party fetch.
    if ".r2.cloudflarestorage.com" in base_url:
        raise ValueError(
            "--r2-public-base-url cannot be a cloudflarestorage API endpoint. "
            "Use a public custom domain or the bucket's r2.dev public URL."
        )


def build_patch_for_field(ref: ImageRef, new_url: str, multi_state: Dict[str, List[str]]) -> dict:
    if ref.source_type == "single":
        return {ref.field_name: new_url}
    if ref.multi_urls is None or ref.multi_index is None:
        return {}
    urls = multi_state.get(ref.field_name)
    if urls is None:
        urls = list(ref.multi_urls)
        multi_state[ref.field_name] = urls
    urls[ref.multi_index] = new_url
    return {ref.field_name: ", ".join(urls)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Preprocess oversize product images (>10MB) for Mercari CSV generation: "
            "resize to 1500x1500 progressive JPEG, upload to Cloudflare R2, and update Baserow URLs."
        )
    )
    parser.add_argument("--token", default=None, help="Baserow database token (optional if env var is set)")
    parser.add_argument("--table-id", type=int, default=912520)
    parser.add_argument("--item-code-field", default="Item Code")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--max-side", type=int, default=1500)
    parser.add_argument("--jpeg-quality", type=int, default=82)
    parser.add_argument("--r2-bucket", default="resize-product-images")
    parser.add_argument("--r2-prefix", default="")
    parser.add_argument("--r2-public-base-url", required=True)
    parser.add_argument("--wrangler-config", default=None)
    parser.add_argument(
        "--item-codes",
        default=None,
        help="Comma-separated item codes or path to newline-separated item-code file",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(os.path.join(SKILL_DIR, ".env"))
    load_dotenv(os.path.join(SKILL_DIR, ".env.local"))

    token = resolve_baserow_token(args.token)
    if not token:
        raise SystemExit(
            "Missing Baserow token. Pass --token or set BASEROW_TOKEN "
            "(optionally in skill .env/.env.local)."
        )

    validate_public_base_url(args.r2_public_base_url)

    bucket = normalize_bucket_name(args.r2_bucket)
    item_codes_filter = parse_item_codes_arg(args.item_codes)

    ensure_bucket_exists(bucket=bucket, wrangler_config=args.wrangler_config, dry_run=args.dry_run)

    if item_codes_filter:
        rows = fetch_rows_by_item_codes(
            token=token,
            table_id=args.table_id,
            item_code_field=args.item_code_field,
            item_codes=item_codes_filter,
        )
    else:
        rows = fetch_table_rows(token, args.table_id)

    updates: List[dict] = []
    report_items: List[dict] = []
    scanned = 0

    for row in rows:
        item_code = str(row.get(args.item_code_field) or "").strip()
        if not item_code:
            continue
        if item_codes_filter and item_code not in item_codes_filter:
            continue

        refs = collect_image_refs(row)
        if not refs:
            continue

        scanned += 1
        row_patch: Dict[str, str] = {}
        multi_state: Dict[str, List[str]] = {}

        for ref in refs:
            cl = head_content_length(ref.url)
            should_process = cl is None or cl > args.max_bytes
            if not should_process:
                continue

            try:
                original_bytes = download_bytes(ref.url)
                if len(original_bytes) <= args.max_bytes:
                    continue
                resized_bytes = resize_to_progressive_jpeg(
                    original_bytes,
                    max_side=args.max_side,
                    quality=args.jpeg_quality,
                )
                key_base = f"{item_code}_{ref.slot:02d}.jpg"
                key = f"{args.r2_prefix.strip('/')}/{item_code}/{key_base}" if args.r2_prefix.strip("/") else f"{item_code}/{key_base}"

                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                    tf.write(resized_bytes)
                    tmp_path = tf.name

                try:
                    upload_via_wrangler(
                        local_file=tmp_path,
                        bucket=bucket,
                        key=key,
                        wrangler_config=args.wrangler_config,
                        dry_run=args.dry_run,
                    )
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                new_url = build_public_url(args.r2_public_base_url, key)
                row_patch.update(build_patch_for_field(ref, new_url, multi_state))

                report_items.append(
                    {
                        "row_id": row.get("id"),
                        "item_code": item_code,
                        "slot": ref.slot,
                        "field": ref.field_name,
                        "old_url": ref.url,
                        "new_url": new_url,
                        "original_bytes": len(original_bytes),
                        "resized_bytes": len(resized_bytes),
                        "r2_key": key,
                    }
                )
            except Exception as exc:
                report_items.append(
                    {
                        "row_id": row.get("id"),
                        "item_code": item_code,
                        "slot": ref.slot,
                        "field": ref.field_name,
                        "old_url": ref.url,
                        "error": str(exc),
                    }
                )

        if row_patch:
            row_patch["id"] = row["id"]
            updates.append(row_patch)

    updated_rows = 0
    if updates and not args.dry_run:
        for i in range(0, len(updates), 100):
            batch = updates[i : i + 100]
            patched = patch_rows(token, args.table_id, batch)
            updated_rows += len(patched)

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
        "items": report_items,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
