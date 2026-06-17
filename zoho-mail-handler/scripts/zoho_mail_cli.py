#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def _xdg_dir(env_key: str, fallback: Path) -> Path:
    value = os.getenv(env_key)
    if value:
        return Path(value).expanduser()
    return fallback


def _cache_dir() -> Path:
    return _xdg_dir("XDG_CACHE_HOME", Path.home() / ".cache") / "zoho-mail-handler"


def _config_path(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    return _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / "zoho-mail-handler" / "config.json"


def _read_json_file(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _find_upwards(start: Path, filename: str, max_levels: int = 10) -> Optional[Path]:
    cur = start.resolve()
    for _ in range(max_levels + 1):
        candidate = cur / filename
        if candidate.exists():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _parse_dotenv(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return out
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        if key and val:
            out[key] = val
    return out


def _load_local_credential_files() -> Dict[str, str]:
    creds: Dict[str, str] = {}
    cwd = Path.cwd()
    dev_env = _find_upwards(cwd, "dev.env")
    if dev_env:
        creds.update(_parse_dotenv(dev_env))
    vars_txt = _find_upwards(cwd, "variables and secrets.txt")
    if vars_txt:
        creds.update(_parse_dotenv(vars_txt))
    return creds


def load_config(explicit_path: Optional[str]) -> Dict[str, Any]:
    path = _config_path(explicit_path)
    cfg = _read_json_file(path)
    local = _load_local_credential_files()

    def pick(env_key: str, local_key: str, cfg_key: str) -> Optional[str]:
        if os.getenv(env_key):
            return os.getenv(env_key)
        if local.get(local_key):
            return local.get(local_key)
        val = cfg.get(cfg_key)
        if val is None:
            return None
        return str(val)

    def coerce_base_url(value: Optional[str], default: str) -> str:
        if not value:
            return default
        v = str(value).strip()
        if v.startswith("http://") or v.startswith("https://"):
            return v
        return f"https://{v}"

    accounts_domain = pick("ZOHO_ACCOUNTS_DOMAIN", "ZOHO_ACCOUNTS_DOMAIN", "accounts_domain") or pick(
        "ACCOUNTS_DOMAIN", "ACCOUNTS_DOMAIN", "accounts_domain"
    )
    return {
        "client_id": pick("ZOHO_CLIENT_ID", "ZOHO_CLIENT_ID", "client_id"),
        "client_secret": pick("ZOHO_CLIENT_SECRET", "ZOHO_CLIENT_SECRET", "client_secret"),
        "refresh_token": pick("ZOHO_REFRESH_TOKEN", "ZOHO_REFRESH_TOKEN", "refresh_token"),
        "accounts_base": coerce_base_url(
            pick("ZOHO_ACCOUNTS_BASE", "ZOHO_ACCOUNTS_BASE", "accounts_base") or accounts_domain or "https://accounts.zoho.com",
            "https://accounts.zoho.com",
        ),
        "mail_api_base": pick("ZOHO_MAIL_API_BASE", "ZOHO_MAIL_API_BASE", "mail_api_base") or "https://mail.zoho.com/api",
        "default_account_id": pick("ZOHO_DEFAULT_ACCOUNT_ID", "ZOHO_DEFAULT_ACCOUNT_ID", "default_account_id")
        or pick("ZOHO_ACCOUNT_ID", "ZOHO_ACCOUNT_ID", "default_account_id"),
        "default_from_address": pick("ZOHO_DEFAULT_FROM_ADDRESS", "ZOHO_DEFAULT_FROM_ADDRESS", "default_from_address"),
    }


def _require(cfg: Dict[str, Any], key: str) -> str:
    value = cfg.get(key)
    if not value:
        raise SystemExit(f"Missing required credential/config: {key}")
    return str(value)


def _http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout_s: int = 30,
) -> Dict[str, Any]:
    req = urllib.request.Request(url, method=method)
    req.add_header("Accept", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if body is not None:
        req.data = body
        if req.get_header("Content-Type") is None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        _eprint(f"HTTP {e.code} {e.reason} for {method} {url}")
        if raw:
            _eprint(raw)
        raise SystemExit(2)
    except urllib.error.URLError as e:
        _eprint(f"Network error for {method} {url}: {e}")
        raise SystemExit(2)


def _token_cache_paths() -> Tuple[Path, Path]:
    cd = _cache_dir()
    cd.mkdir(parents=True, exist_ok=True)
    return cd / "token.json", cd / "last_search.json"


def _now_epoch() -> int:
    return int(time.time())


def get_access_token(cfg: Dict[str, Any]) -> str:
    token_path, _ = _token_cache_paths()
    cached = _read_json_file(token_path)
    access_token = cached.get("access_token")
    expires_at = cached.get("expires_at")
    if access_token and isinstance(expires_at, int) and expires_at - 60 > _now_epoch():
        return str(access_token)

    client_id = _require(cfg, "client_id")
    client_secret = _require(cfg, "client_secret")
    refresh_token = _require(cfg, "refresh_token")
    accounts_base = _require(cfg, "accounts_base").rstrip("/")

    token_url = f"{accounts_base}/oauth/v2/token"
    body = urllib.parse.urlencode(
        {
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")

    data = _http_json("POST", token_url, body=body)
    new_token = data.get("access_token")
    expires_in = data.get("expires_in")
    if not new_token:
        _eprint("Failed to obtain access token. Response:")
        _eprint(json.dumps(data, indent=2))
        raise SystemExit(2)

    try:
        ttl = int(expires_in) if expires_in is not None else 3600
    except Exception:
        ttl = 3600

    token_path.write_text(
        json.dumps(
            {
                "access_token": new_token,
                "expires_at": _now_epoch() + ttl,
            }
        ),
        encoding="utf-8",
    )
    return str(new_token)


def zoho_headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    token = get_access_token(cfg)
    return {"Authorization": f"Zoho-oauthtoken {token}"}


def _api_base(cfg: Dict[str, Any]) -> str:
    return _require(cfg, "mail_api_base").rstrip("/")


def api_get(cfg: Dict[str, Any], path: str, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = _api_base(cfg)
    url = f"{base}/{path.lstrip('/')}"
    if query:
        url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    return _http_json("GET", url, headers=zoho_headers(cfg))


def api_post_json(cfg: Dict[str, Any], path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    base = _api_base(cfg)
    url = f"{base}/{path.lstrip('/')}"
    body = json.dumps(payload).encode("utf-8")
    headers = zoho_headers(cfg)
    headers["Content-Type"] = "application/json"
    return _http_json("POST", url, headers=headers, body=body)


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        if data and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return "\n".join(self._chunks)


def html_to_text(html: str) -> str:
    parser = _HTMLText()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return html
    return parser.text()


def _maybe_quote(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v
    if any(ch.isspace() for ch in v):
        return f'"{v}"'
    return v


def _date_to_zoho(value: str) -> str:
    v = value.strip()
    if not v:
        return v
    if "-" not in v and len(v) >= 9:
        return v
    try:
        d = dt.date.fromisoformat(v)
    except ValueError:
        return v
    return d.strftime("%d-%b-%Y")


def build_search_key(args: argparse.Namespace) -> str:
    if args.search_key:
        return args.search_key.strip()

    parts: list[str] = []
    if args.entire:
        parts.append(f'entire:{_maybe_quote(args.entire)}')
    if args.content:
        parts.append(f'content:{_maybe_quote(args.content)}')
    if args.sender:
        parts.append(f"sender:{args.sender.strip()}")
    if args.to:
        parts.append(f"to:{args.to.strip()}")
    if args.cc:
        parts.append(f"cc:{args.cc.strip()}")
    if args.subject:
        parts.append(f'subject:{_maybe_quote(args.subject)}')
    if args.in_folder:
        parts.append(f'in:{_maybe_quote(args.in_folder)}')
    if args.label:
        parts.append(f'label:{_maybe_quote(args.label)}')
    if args.has_attachment:
        parts.append("has:attachment")
    if args.from_date:
        parts.append(f"fromDate:{_date_to_zoho(args.from_date)}")
    if args.to_date:
        parts.append(f"toDate:{_date_to_zoho(args.to_date)}")
    if args.include_spam_trash:
        parts.append("inclspamtrash:true")

    if not parts:
        raise SystemExit("Provide either --search-key or at least one search criterion like --sender/--subject/--entire.")

    return "::".join(parts)


def cmd_accounts(cfg: Dict[str, Any], _args: argparse.Namespace) -> None:
    data = api_get(cfg, "/accounts")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_folders(cfg: Dict[str, Any], args: argparse.Namespace) -> None:
    account_id = args.account_id or cfg.get("default_account_id")
    if not account_id:
        raise SystemExit("Missing --account-id (or set ZOHO_DEFAULT_ACCOUNT_ID).")
    data = api_get(cfg, f"/accounts/{account_id}/folders")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _cache_last_search(payload: Dict[str, Any]) -> None:
    _, last_search_path = _token_cache_paths()
    last_search_path.write_text(json.dumps(payload), encoding="utf-8")


def _get_last_search() -> Dict[str, Any]:
    _, last_search_path = _token_cache_paths()
    return _read_json_file(last_search_path)


def _lookup_message_from_last_search(message_id: str) -> Optional[Dict[str, Any]]:
    data = _get_last_search()
    items = data.get("data")
    if not isinstance(items, list):
        return None
    for item in items:
        if str(item.get("messageId")) == str(message_id):
            return item
    return None


def cmd_search(cfg: Dict[str, Any], args: argparse.Namespace) -> None:
    account_id = args.account_id or cfg.get("default_account_id")
    if not account_id:
        raise SystemExit("Missing --account-id (or set ZOHO_DEFAULT_ACCOUNT_ID).")

    search_key = build_search_key(args)
    query: Dict[str, Any] = {
        "searchKey": search_key,
        "receivedTime": args.received_time,
        "start": args.start,
        "limit": args.limit,
        "includeto": "true" if args.include_to else "false",
    }
    data = api_get(cfg, f"/accounts/{account_id}/messages/search", query=query)

    if args.with_content:
        items = data.get("data")
        if isinstance(items, list):
            for item in items:
                folder_id = item.get("folderId")
                message_id = item.get("messageId")
                if not folder_id or not message_id:
                    continue
                content_data = api_get(
                    cfg,
                    f"/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/content",
                )
                content_html = (content_data.get("data") or {}).get("content") or ""
                content_plain = html_to_text(str(content_html))
                if args.content_limit_chars and len(content_plain) > args.content_limit_chars:
                    content_plain = content_plain[: args.content_limit_chars] + "\n...[truncated]"
                item["content_plain"] = content_plain

    _cache_last_search(data)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_content(cfg: Dict[str, Any], args: argparse.Namespace) -> None:
    account_id = args.account_id or cfg.get("default_account_id")
    if not account_id:
        raise SystemExit("Missing --account-id (or set ZOHO_DEFAULT_ACCOUNT_ID).")
    if not args.folder_id:
        raise SystemExit("Missing --folder-id.")
    if not args.message_id:
        raise SystemExit("Missing --message-id.")
    query = {"includeBlockContent": "true" if args.include_block_content else "false"}
    data = api_get(
        cfg,
        f"/accounts/{account_id}/folders/{args.folder_id}/messages/{args.message_id}/content",
        query=query,
    )
    if args.plain:
        content_html = (data.get("data") or {}).get("content") or ""
        data["data"] = dict(data.get("data") or {})
        data["data"]["content_plain"] = html_to_text(str(content_html))
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _read_text_file(path: str) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8")


def _normalize_reply_subject(original_subject: str) -> str:
    s = original_subject.strip()
    if not s:
        return s
    lower = s.lower()
    if lower.startswith("re:"):
        return s
    return f"Re: {s}"


def cmd_reply(cfg: Dict[str, Any], args: argparse.Namespace) -> None:
    account_id = args.account_id or cfg.get("default_account_id")
    if not account_id:
        raise SystemExit("Missing --account-id (or set ZOHO_DEFAULT_ACCOUNT_ID).")
    if not args.message_id:
        raise SystemExit("Missing --message-id.")

    from_address = args.from_address or cfg.get("default_from_address")
    if not from_address:
        raise SystemExit("Missing --from-address (or set ZOHO_DEFAULT_FROM_ADDRESS/default_from_address).")

    to_address = args.to_address
    subject = args.subject
    if args.use_last_search and (not to_address or not subject):
        item = _lookup_message_from_last_search(str(args.message_id))
        if item:
            if not to_address:
                to_address = item.get("fromAddress")
            if not subject:
                subject = _normalize_reply_subject(str(item.get("subject") or ""))

    if not to_address:
        raise SystemExit("Missing --to-address (and could not resolve from cached last search).")
    if not subject:
        raise SystemExit("Missing --subject (and could not resolve from cached last search).")

    if args.content_file:
        content = _read_text_file(args.content_file)
    elif args.content is not None:
        content = args.content
    else:
        raise SystemExit("Missing --content or --content-file.")

    payload: Dict[str, Any] = {
        "fromAddress": from_address,
        "toAddress": to_address,
        "subject": subject,
        "content": content,
        "action": "reply",
        "mailFormat": args.mail_format,
        "encoding": args.encoding,
    }
    if args.ask_receipt:
        payload["askReceipt"] = args.ask_receipt
    if args.cc_address:
        payload["ccAddress"] = args.cc_address
    if args.bcc_address:
        payload["bccAddress"] = args.bcc_address

    if args.dry_run:
        print(json.dumps({"path": f"/accounts/{account_id}/messages/{args.message_id}", "payload": payload}, indent=2, ensure_ascii=False))
        return

    data = api_post_json(cfg, f"/accounts/{account_id}/messages/{args.message_id}", payload)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(prog="zoho_mail_cli.py")
    parser.add_argument("--config", help="Optional path to config.json (defaults to ~/.config/zoho-mail-handler/config.json)")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_accounts = sub.add_parser("accounts", help="List Zoho Mail accounts for the authenticated user")
    p_accounts.set_defaults(fn=cmd_accounts)

    p_folders = sub.add_parser("folders", help="List folders for an account")
    p_folders.add_argument("--account-id")
    p_folders.set_defaults(fn=cmd_folders)

    p_search = sub.add_parser("search", help="Search emails and optionally fetch content for each result")
    p_search.add_argument("--account-id")
    p_search.add_argument("--search-key", help="Raw Zoho searchKey string (overrides other search flags)")
    p_search.add_argument("--entire", help="Search word/phrase anywhere in email")
    p_search.add_argument("--content", help="Search within email content")
    p_search.add_argument("--sender", help="Search by sender (email or keyword)")
    p_search.add_argument("--to", help="Search by To address")
    p_search.add_argument("--cc", help="Search by Cc address")
    p_search.add_argument("--subject", help="Search by subject")
    p_search.add_argument("--in-folder", help="Search within a folder name (e.g., Inbox)")
    p_search.add_argument("--label", help="Search within a label/tag name")
    p_search.add_argument("--has-attachment", action="store_true", help="Filter to emails that have attachments")
    p_search.add_argument("--from-date", help="YYYY-MM-DD (or Zoho DD-Mmm-YYYY)")
    p_search.add_argument("--to-date", help="YYYY-MM-DD (or Zoho DD-Mmm-YYYY)")
    p_search.add_argument("--include-spam-trash", action="store_true", help="Include Spam and Trash in results")
    p_search.add_argument("--received-time", type=int, help="Unix timestamp in milliseconds; defaults to 'now - 2 minutes' on Zoho side")
    p_search.add_argument("--start", type=int, default=1)
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--include-to", action="store_true")
    p_search.add_argument("--with-content", action="store_true", help="Fetch /content for each result and add content_plain")
    p_search.add_argument("--content-limit-chars", type=int, default=8000, help="Truncate content_plain to this many chars (0 disables truncation)")
    p_search.set_defaults(fn=cmd_search)

    p_content = sub.add_parser("content", help="Fetch email content")
    p_content.add_argument("--account-id")
    p_content.add_argument("--folder-id", required=True)
    p_content.add_argument("--message-id", required=True)
    p_content.add_argument("--include-block-content", action="store_true")
    p_content.add_argument("--plain", action="store_true", help="Add content_plain derived from HTML content")
    p_content.set_defaults(fn=cmd_content)

    p_reply = sub.add_parser("reply", help="Reply to a specific email by messageId")
    p_reply.add_argument("--account-id")
    p_reply.add_argument("--message-id", required=True)
    p_reply.add_argument("--from-address")
    p_reply.add_argument("--to-address")
    p_reply.add_argument("--cc-address")
    p_reply.add_argument("--bcc-address")
    p_reply.add_argument("--subject")
    p_reply.add_argument("--content")
    p_reply.add_argument("--content-file")
    p_reply.add_argument("--mail-format", default="plaintext", choices=["plaintext", "html"])
    p_reply.add_argument("--encoding", default="UTF-8")
    p_reply.add_argument("--ask-receipt", choices=["yes", "no"])
    p_reply.add_argument("--no-last-search", dest="use_last_search", action="store_false", help="Do not use cached last search to resolve To/Subject")
    p_reply.set_defaults(use_last_search=True)
    p_reply.add_argument("--dry-run", action="store_true")
    p_reply.set_defaults(fn=cmd_reply)

    args = parser.parse_args()
    cfg = load_config(args.config)
    args.fn(cfg, args)


if __name__ == "__main__":
    main()
