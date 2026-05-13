#!/usr/bin/env bash
# Bootstrap pptx skill dependencies (idempotent, cross-platform).
#
# - Safe to call before every run; skips work when already installed.
# - Stamp fingerprint includes: package.json hash + node major version +
#   platform + arch. Any change triggers a clean reinstall, which avoids
#   silent breakage when sharp's prebuilt binary no longer matches the
#   current Node ABI / OS / CPU architecture.
# - Works on macOS (zsh/bash), Linux (bash), and Git Bash on Windows.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SKILL_DIR"

# ─── Preflight ───────────────────────────────────────────
if ! command -v node >/dev/null 2>&1; then
  echo "[bootstrap] ERROR: node not found in PATH" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "[bootstrap] ERROR: npm not found in PATH" >&2
  exit 1
fi

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "[bootstrap] ERROR: Node >= 18.17 required, got $(node -v)" >&2
  exit 1
fi

# ─── Cross-platform sha256 of package.json ───────────────
hash_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    # Fallback: use node
    node -e "const c=require('crypto'),f=require('fs');console.log(c.createHash('sha256').update(f.readFileSync('$1')).digest('hex'))"
  fi
}

PKG_HASH="$(hash_file package.json)"
PLATFORM="$(node -p 'process.platform')"
ARCH="$(node -p 'process.arch')"
FINGERPRINT="${PKG_HASH}|node${NODE_MAJOR}|${PLATFORM}-${ARCH}"

STAMP_DIR="node_modules/.cache"
STAMP_FILE="${STAMP_DIR}/pptx-bootstrap.stamp"

# ─── Skip if up-to-date ──────────────────────────────────
if [ -f "$STAMP_FILE" ] && [ "$(cat "$STAMP_FILE" 2>/dev/null || true)" = "$FINGERPRINT" ]; then
  echo "[bootstrap] up-to-date (${PLATFORM}-${ARCH}, node${NODE_MAJOR})"
  exit 0
fi

# ─── Reinstall ───────────────────────────────────────────
echo "[bootstrap] installing node deps for ${PLATFORM}-${ARCH} (node${NODE_MAJOR})..."

# If fingerprint changed, drop old node_modules so sharp reinstalls fresh
# binaries for the current platform/Node ABI.
if [ -f "$STAMP_FILE" ]; then
  echo "[bootstrap] fingerprint changed, removing old node_modules..."
  rm -rf node_modules
fi

# Prefer npm ci when a lock file exists (reproducible & faster);
# fall back to npm install on first run.
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund --loglevel=error
else
  npm install --no-audit --no-fund --loglevel=error
fi

# ─── Playwright Chromium (separate ~150MB download) ─────
echo "[bootstrap] ensuring Playwright Chromium is installed..."
# `--with-deps` only works on Linux; skip elsewhere to avoid sudo prompt.
if [ "$PLATFORM" = "linux" ]; then
  npx --yes playwright install --with-deps chromium || npx --yes playwright install chromium
else
  npx --yes playwright install chromium
fi

# ─── Smoke test: can we actually require the deps? ──────
echo "[bootstrap] verifying installation..."
node -e "
  require('pptxgenjs');
  require('playwright');
  require('sharp');
  console.log('[bootstrap] all deps require() OK');
"

# ─── Persist stamp ───────────────────────────────────────
mkdir -p "$STAMP_DIR"
printf '%s' "$FINGERPRINT" > "$STAMP_FILE"
echo "[bootstrap] done"
