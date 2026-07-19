#!/usr/bin/env python3
"""Supabase access layer for mercari-csv-listing — replaces Baserow REST API.

Provides a compatibility layer that returns rows with Baserow-style field names
(e.g. "Product Name", "Unit Price") so existing script logic works with minimal
changes.

Two backends:
  - supabase-py (default, needs IPv6-to-origin or pooler)
  - psycopg2 pooler (MacBook IPv4 fallback, port 6543)

Usage:
    from supabase_db import SupabaseDB

    db = SupabaseDB()
    rows = db.fetch_by_item_codes(["SKU001", "SKU002"])
    # rows is dict[item_code, dict] with Baserow-compatible field names

    db.update_mercari_category_id("SKU001", "12345")
    db.update_representative_color_ja("SKU002", "ホワイト")
    db.update_image_urls_json("SKU003", ["https://...", "https://..."])

Environment:
    SUPABASE_URL              — https://<project-ref>.supabase.co
    SUPABASE_SERVICE_ROLE_KEY — service_role key
    SUPABASE_USE_POOLER       — set to "1" to use psycopg2 pooler (MacBook)
    SUPABASE_POOLER_HOST      — pooler host (default: aws-0-ap-northeast-2.pooler.supabase.com)
    SUPABASE_POOLER_PORT      — pooler port (default: 6543)
    SUPABASE_DB_PASSWORD      — database password for pooler mode
"""

import os
import sys
import json
from typing import Dict, List, Optional

# Try supabase-py first
try:
    from supabase import create_client
    HAS_SUPABASE_PY = True
except ImportError:
    HAS_SUPABASE_PY = False

# Try psycopg2 for pooler mode
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


def _load_env():
    """Load .env from the skill directory."""
    env = {}
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


ENV = _load_env()

SUPABASE_URL = ENV.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = ENV.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
USE_POOLER = ENV.get("SUPABASE_USE_POOLER", os.environ.get("SUPABASE_USE_POOLER", "")) == "1"
POOLER_HOST = ENV.get("SUPABASE_POOLER_HOST", os.environ.get("SUPABASE_POOLER_HOST",
                        "aws-1-ap-northeast-2.pooler.supabase.com"))
POOLER_PORT = int(ENV.get("SUPABASE_POOLER_PORT", os.environ.get("SUPABASE_POOLER_PORT", "5432")))
POOLER_USER = ENV.get("SUPABASE_POOLER_USER", os.environ.get("SUPABASE_POOLER_USER",
                        "postgres.gqeyfhshxdiyhugvmbuk"))
DB_PASSWORD = ENV.get("SUPABASE_DB_PASSWORD", os.environ.get("SUPABASE_DB_PASSWORD", ""))


class SupabaseDB:
    """Supabase data access with Baserow-compatible field name mapping.

    Returns rows keyed by Baserow 886994 field names so existing mercari scripts
    can access data with familiar keys like row["Product Name"], row["Unit Price"].
    """

    def __init__(self):
        self._client = None
        self._conn = None

        if USE_POOLER:
            self._init_pooler()
        else:
            self._init_rest()

    def _init_rest(self):
        if not HAS_SUPABASE_PY:
            raise ImportError("supabase-py not installed. Run: pip install supabase")
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        self._client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def _init_pooler(self):
        if not HAS_PSYCOPG2:
            raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")
        if not DB_PASSWORD:
            raise ValueError("SUPABASE_DB_PASSWORD required for pooler mode")
        self._conn = psycopg2.connect(
            host=POOLER_HOST,
            port=POOLER_PORT,
            dbname="postgres",
            user=POOLER_USER,
            password=DB_PASSWORD,
            connect_timeout=10,
        )

    # ─── Read methods ──────────────────────────────────────────

    def fetch_by_item_codes(self, codes: List[str]) -> Dict[str, dict]:
        """Fetch rows from baserow_886994_compat_vw for given item codes.

        Returns dict[item_code, row_dict] where row_dict has Baserow-compatible
        field names (e.g. "Product Name", "Unit Price", "Image URLs JSON").
        """
        if not codes:
            return {}

        if self._conn:
            return self._fetch_by_codes_pg(codes)
        return self._fetch_by_codes_rest(codes)

    def _fetch_by_codes_rest(self, codes: List[str]) -> Dict[str, dict]:
        """Fetch via supabase-py REST API with pagination."""
        result = {}
        page_size = 200

        client = self._client
        for i in range(0, len(codes), page_size):
            batch = codes[i:i + page_size]
            resp = (client.table("baserow_886994_compat_vw")
                    .select("*")
                    .in_("item_code", batch)
                    .execute())
            for row in (resp.data or []):
                ic = (row.get("item_code") or "").strip()
                if ic:
                    # JSONB columns come as Python objects — serialize for compat
                    row = self._normalize_row(row)
                    result[ic] = row
        return result

    def _fetch_by_codes_pg(self, codes: List[str]) -> Dict[str, dict]:
        """Fetch via psycopg2 pooler."""
        result = {}
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                'SELECT * FROM baserow_886994_compat_vw WHERE item_code = ANY(%s)',
                (codes,)
            )
            for row in cur.fetchall():
                ic = (row.get("item_code") or "").strip()
                if ic:
                    row = self._normalize_row(row)
                    result[ic] = row
        finally:
            cur.close()
        return result

    def _normalize_row(self, row: dict) -> dict:
        """Normalize a Supabase row for Baserow compatibility.

        - Serialize JSONB fields (image_urls_json) to JSON strings
        - Ensure all expected field keys exist
        """
        # JSONB columns come as Python lists/dicts — serialize to JSON string
        # for backward compat with existing code that expects strings
        for key in list(row.keys()):
            val = row.get(key)
            if isinstance(val, (list, dict)):
                row[key] = json.dumps(val, ensure_ascii=False)

        # Ensure "item code" (lowercase) exists for code that uses r.get("item code")
        if row.get("item_code") and not row.get("item code"):
            row["item code"] = row["item_code"]

        return row

    # ─── Write methods ─────────────────────────────────────────

    def update_mercari_category_id(self, item_code: str, category_id: str) -> bool:
        """Update mercari_category_id on product_variants."""
        return self._update_variant(item_code, {"mercari_category_id": category_id})

    def update_representative_color_ja(self, item_code: str, color_ja: str) -> bool:
        """Update representative_color_ja on product_variants."""
        return self._update_variant(item_code, {"representative_color_ja": color_ja})

    def update_image_urls_json(self, item_code: str, urls: list) -> bool:
        """Update image_urls_json (JSONB) on product_variants."""
        return self._update_variant(item_code, {"image_urls_json": urls})

    def _update_variant(self, item_code: str, data: dict) -> bool:
        """Low-level update on product_variants by item_code."""
        try:
            if self._conn:
                cur = self._conn.cursor()
                try:
                    set_clause = ", ".join(f"{k} = %s" for k in data)
                    values = list(data.values()) + [item_code]
                    cur.execute(
                        f"UPDATE product_variants SET {set_clause} WHERE item_code = %s",
                        values
                    )
                    self._conn.commit()
                    return cur.rowcount > 0
                finally:
                    cur.close()
            else:
                self._client.table("product_variants") \
                    .update(data) \
                    .eq("item_code", item_code) \
                    .execute()
                return True
        except Exception as e:
            sys.stderr.write(f"  WARN: _update_variant({item_code}): {e}\n")
            return False

    def batch_update_variants(self, items: List[dict]) -> int:
        """Batch update product_variants. Each item must have 'item_code'.

        items: [{"item_code": "SKU1", "mercari_category_id": "123"}, ...]
        Returns count of updated rows.
        """
        if not items:
            return 0
        updated = 0
        for item in items:
            code = item.pop("item_code", None)
            if code and item:
                if self._update_variant(code, item):
                    updated += 1
        return updated

    def close(self):
        """Close connection (pooler mode only)."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Convenience — resolve credentials similar to old resolve_token()
def resolve_credentials(cli_key: Optional[str] = None) -> str:
    """Resolve Supabase service_role key from CLI or env."""
    if cli_key:
        return cli_key.strip()
    return SUPABASE_KEY or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
