# Image Preprocessing and R2 Write-Back (Mercari CSV)

## Goal

Before generating the Mercari listing CSV, detect any product image over `10MB`, resize it to `1500x1500` progressive JPEG, upload to Cloudflare R2, and update the source URL back into Baserow table `912520`.

## Bucket naming

Cloudflare R2 bucket names cannot contain spaces.

- requested display name: `Resize Product Images`
- effective bucket name (recommended): `resize-product-images`

## Required runtime inputs

- Baserow token: `BASEROW_TOKEN` env var (or pass `--token`)
- R2 public URL base for the bucket (custom domain or r2.dev): `R2_PUBLIC_BASE_URL`
- Optional wrangler config path: `WRANGLER_CONFIG`

Note:

- `https://<account-id>.r2.cloudflarestorage.com/...` is an API endpoint, not a public object URL for Mercari image fetch.
- Use a public custom domain or `https://pub-xxxx.r2.dev` as `R2_PUBLIC_BASE_URL`.

## Create/ensure bucket

```bash
bash scripts/create_resize_product_images_bucket.sh "Resize Product Images" "$WRANGLER_CONFIG"
```

## Dry run for selected item codes

```bash
python3 scripts/prepare_oversize_images_for_mercari.py \
  --table-id 912520 \
  --item-codes "N512P206612B,N512P403841B" \
  --r2-bucket "Resize Product Images" \
  --r2-public-base-url "$R2_PUBLIC_BASE_URL" \
  --wrangler-config "$WRANGLER_CONFIG" \
  --dry-run
```

## Production run

```bash
python3 scripts/prepare_oversize_images_for_mercari.py \
  --table-id 912520 \
  --r2-bucket "Resize Product Images" \
  --r2-public-base-url "$R2_PUBLIC_BASE_URL" \
  --wrangler-config "$WRANGLER_CONFIG"
```

## Performance

- Uses `requests.Session` for HTTP connection reuse.
- `ThreadPoolExecutor` (default 10 workers) for parallel image download, resize, and R2 upload.
- Typical speedup: ~560s → ~55s for a full catalog run.
- Control parallelism with `--workers N`.
- Skip HEAD pre-checks with `--skip-head-check` (avoids ~11k HEAD calls; downloads every image and checks size after).
- Skip HEAD for specific hosts with `--head-check-skip-hosts "cdn.giga.com,img.shop.com"`.

## Output behavior

- Image naming convention: `ItemCode_01.jpg`, `ItemCode_02.jpg`, ...
- R2 object key pattern: `<prefix>/<ItemCode>/<ItemCode>_NN.jpg` (prefix optional)
- Only images above `10MB` are replaced.
- Baserow write-back updates only fields that were replaced.
- JSON report is printed to stdout with replaced slots and errors.
- Output includes `workers`, `skip_head_check`, and `head_check_skip_hosts` in the report.

## Performance note

- When `--item-codes` is provided, the script uses Baserow server-side exact filter on `Item Code` instead of scanning all pages.
- Run without `--item-codes` only when you intentionally want full-table processing.
