"""Shared utilities for Mercari listing text processing and GigaB2B API access."""
from __future__ import annotations

import base64
import hashlib
import hmac
import html.parser
import json
import os
import random
import re
import time
import urllib.request
from typing import Dict, List, Optional


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ")).strip()


def strip_html(text: str) -> str:
    if not text or "<" not in text:
        return text

    class _MLStripper(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.reset()
            self._parts: List[str] = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript"):
                self._skip = False
            if tag in ("div", "p", "tr", "li", "br", "h1", "h2", "h3", "h4", "h5"):
                self._parts.append("\n")

        def handle_data(self, data):
            if not self._skip:
                stripped = data.strip()
                if stripped:
                    self._parts.append(stripped)

    stripper = _MLStripper()
    try:
        stripper.feed(text)
    except Exception:
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"&[a-z]+;", " ", clean)
        return normalize_spaces(clean)

    raw = " ".join(stripper._parts)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return normalize_spaces(raw)


def _ms_timestamp() -> str:
    return str(int(time.time() * 1000))


def _nonce_10() -> str:
    return f"{random.randint(10**9, 10**10 - 1)}"


def _giga_sign(client_id: str, client_secret: str, api_path: str, timestamp: str, nonce: str) -> str:
    message = f"{client_id}&{api_path}&{timestamp}&{nonce}"
    key = f"{client_id}&{client_secret}&{nonce}"
    digest = hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.b64encode(digest.encode("utf-8")).decode("utf-8")


def _giga_post(path: str, body: dict, timeout: int = 60) -> dict:
    base_url = os.getenv("GIGA_API_BASE_URL", "https://openapi.gigab2b.com").rstrip("/")
    client_id = os.getenv("GIGA_CLIENT_ID", "").strip()
    client_secret = os.getenv("GIGA_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Missing GIGA_CLIENT_ID or GIGA_CLIENT_SECRET")

    api_path = "/" + path.lstrip("/")
    ts = _ms_timestamp()
    nonce = _nonce_10()
    sign = _giga_sign(client_id, client_secret, api_path, ts, nonce)
    url = f"{base_url}{api_path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "client-id": client_id,
        "timestamp": ts,
        "nonce": nonce,
        "sign": sign,
    }
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_characteristic_prefix(text: str) -> str:
    s = str(text).strip()
    s = re.sub(r"^◎\d+\s*", "", s)
    s = re.sub(r"^◎\d+【[^】]*】\s*", "", s)
    return s.strip()


def fetch_giga_product_features(item_codes: List[str]) -> Dict[str, str]:
    if not item_codes:
        return {}
    try:
        resp = _giga_post(
            "/b2b-overseas-api/v1/buyer/product/detailInfo/v1",
            {"skus": item_codes},
            timeout=120,
        )
    except Exception:
        return {}

    data_list = resp.get("data") if isinstance(resp, dict) else resp
    if not isinstance(data_list, list):
        return {}

    result: Dict[str, str] = {}
    for detail in data_list:
        sku = detail.get("sku") if isinstance(detail, dict) else None
        characteristics = detail.get("characteristics") if isinstance(detail, dict) else []
        if sku and characteristics and isinstance(characteristics, list):
            cleaned = []
            for c in characteristics:
                stripped = _strip_characteristic_prefix(str(c))
                if stripped:
                    cleaned.append(f"・{stripped}")
            if cleaned:
                result[sku] = "\n".join(cleaned)
    return result


def enrich_description_with_llm(
    product_name: str,
    base_desc: str,
    features_text: str,
    dimensions_text: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> str:
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or not product_name:
        return base_desc

    context_parts = [f"商品名: {product_name}"]
    if features_text:
        features_clean = features_text.replace("\n", " ").strip()
        context_parts.append(f"特徴: {features_clean}")
    if dimensions_text:
        context_parts.append(f"サイズ: {dimensions_text}")
    if base_desc and len(base_desc) > 20:
        context_parts.append(f"既存の説明: {base_desc}")

    context = "\n".join(context_parts)

    prompt = (
        "以下の商品情報をもとに、Mercari（メルカリ）向けの商品説明文を生成してください。\n"
        "要件：\n"
        "- 日本語で記述（です・ます調）\n"
        "- 見出し（【商品説明】など）は含めない\n"
        "- 箇条書きではなく自然な文章で\n"
        "- 200〜400文字程度にまとめる\n"
        "- 商品の特徴やメリットを具体的に伝える\n"
        "- 装飾的な表現は避け、簡潔に\n\n"
        f"{context}\n\n"
        "商品説明（本文のみ出力）："
    )

    try:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": "あなたはMercari出品のための日本語商品説明を作成する専門家です。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.5,
            "max_tokens": 600,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if content and len(content) > 20:
            return normalize_spaces(content)
    except Exception:
        pass

    return base_desc
