#!/usr/bin/env python3
"""Signed GigaB2B OpenAPI request helper.

Usage:
  giga_request.py /b2b-overseas-api/v1/buyer/product/price/v1 --body '{"skus":["ABC"]}'
  giga_request.py /b2b-overseas-api/v1/buyer/product/detailInfo/v1 --body @body.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import random
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_body(value: str | None) -> bytes | None:
    if not value:
        return None
    if value.startswith("@"):
        return Path(value[1:]).read_bytes()
    obj = json.loads(value)
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def generate_nonce() -> str:
    return f"{random.randint(10**9, 10**10 - 1)}"


def sign(client_id: str, client_secret: str, api_path: str, timestamp: str, nonce: str) -> str:
    message = f"{client_id}&{api_path}&{timestamp}&{nonce}"
    key = f"{client_id}&{client_secret}&{nonce}"
    digest = hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.b64encode(digest.encode("utf-8")).decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a signed GigaB2B OpenAPI request.")
    parser.add_argument("path", help="API path, for example /b2b-overseas-api/v1/buyer/product/price/v1")
    parser.add_argument("--body", help="JSON body string or @file.json", default=None)
    parser.add_argument("--base-url", default=os.getenv("GIGA_API_BASE_URL", "https://openapi.gigab2b.com"))
    parser.add_argument("--method", default="POST")
    args = parser.parse_args()

    client_id = os.getenv("GIGA_CLIENT_ID") or os.getenv("Giga Client ID")
    client_secret = os.getenv("GIGA_CLIENT_SECRET") or os.getenv("Giga Client Secret")

    if not client_id or not client_secret:
        print("Missing GIGA_CLIENT_ID or GIGA_CLIENT_SECRET.", file=sys.stderr)
        return 2

    api_path = "/" + args.path.lstrip("/")
    timestamp = str(int(time.time() * 1000))
    nonce = generate_nonce()
    signature = sign(client_id, client_secret, api_path, timestamp, nonce)

    url = f"{args.base_url.rstrip('/')}{api_path}"
    headers = {
        "Content-Type": "application/json",
        "client-id": client_id,
        "timestamp": timestamp,
        "nonce": nonce,
        "sign": signature,
    }

    body = load_body(args.body)
    request = Request(url, data=body, headers=headers, method=args.method.upper())

    try:
        with urlopen(request) as response:
            payload = response.read().decode("utf-8", errors="replace")
            print(payload)
            return 0
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        print(payload, file=sys.stderr)
        return exc.code
    except URLError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
