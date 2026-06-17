#!/usr/bin/env bash
set -euo pipefail

# Cloudflare R2 bucket names cannot contain spaces.
# Input like "Resize Product Images" will be normalized to "resize-product-images".
RAW_NAME="${1:-Resize Product Images}"
WRANGLER_CONFIG="${2:-}"

NORMALIZED_NAME="$(echo "$RAW_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/ /-/g; s/[^a-z0-9.-]/-/g; s/-+/-/g; s/^[.-]+//; s/[.-]+$//')"

if [[ -z "$NORMALIZED_NAME" ]]; then
  echo "Invalid bucket name after normalization: $RAW_NAME" >&2
  exit 1
fi

if [[ -n "$WRANGLER_CONFIG" ]]; then
  wrangler r2 bucket create "$NORMALIZED_NAME" --config "$WRANGLER_CONFIG" || true
else
  wrangler r2 bucket create "$NORMALIZED_NAME" || true
fi

echo "$NORMALIZED_NAME"
