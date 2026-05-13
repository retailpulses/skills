---
name: zoho-mail-handler
description: "Use for Zoho Mail REST API work: search emails by keyword/topic/sender and summarize results, fetch email content by messageId, and draft/preview/send replies to a specific email via the Zoho Mail reply endpoint."
---

# Zoho Mail Handler

## Overview

This skill provides a safe workflow + helper CLI for Zoho Mail REST APIs: search email by topic/keyword/sender, summarize matching results, and reply to a specific email (by messageId) once you have explicit user confirmation.

## Credentials (required)

This skill loads credentials in this order:

1. Current process environment
2. `dev.env` (searched upward from the current working directory)
3. `variables and secrets.txt` (searched upward from the current working directory)
4. Optional `~/.config/zoho-mail-handler/config.json`

When generating the refresh token, include scopes that cover what you need (typical minimum):

- `ZohoMail.accounts.READ`
- `ZohoMail.folders.READ`
- `ZohoMail.messages.READ`
- `ZohoMail.messages.CREATE`

### Environment variables

- `ZOHO_CLIENT_ID` (OAuth client id)
- `ZOHO_CLIENT_SECRET` (OAuth client secret)
- `ZOHO_REFRESH_TOKEN` (OAuth refresh token)
- `ZOHO_ACCOUNTS_BASE` (optional; default `https://accounts.zoho.com` — use the `accounts-server` value from Zoho’s OAuth callback for non‑US regions)
- `ZOHO_MAIL_API_BASE` (optional; default `https://mail.zoho.com/api` — set this to your data-center mail host if needed)
- `ZOHO_DEFAULT_ACCOUNT_ID` (optional; used when you don’t pass `--account-id`)
- `ZOHO_DEFAULT_FROM_ADDRESS` (optional; used when replying if you don’t pass `--from-address`)

Never print or paste these values into chat logs, commit them to git, or store them in workspace files.

### Optional config file

If you prefer a file, create:

- `~/.config/zoho-mail-handler/config.json`

Supported keys (env vars override file):

```json
{
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "...",
  "accounts_base": "https://accounts.zoho.com",
  "mail_api_base": "https://mail.zoho.com/api",
  "default_account_id": "123456789",
  "default_from_address": "me@mydomain.com"
}
```

## Quick start (CLI)

Helper CLI: `scripts/zoho_mail_cli.py`

- List accounts: `python3 scripts/zoho_mail_cli.py accounts`
- List folders: `python3 scripts/zoho_mail_cli.py folders --account-id <accountId>`
- Search emails: `python3 scripts/zoho_mail_cli.py search --account-id <accountId> --sender someone@example.com --subject "invoice" --limit 10 --with-content`
- Fetch one email’s content: `python3 scripts/zoho_mail_cli.py content --account-id <accountId> --folder-id <folderId> --message-id <messageId> --plain`

## Task 1: Search and summarize emails (topic/keyword/sender)

### Workflow

1. Build a Zoho `searchKey` using their search syntax (see `references/search_syntax.md`).
2. Run `search` with `--with-content` for the top N results you want to summarize.
3. Summarize in your final response:
   - 1–2 line overall summary of what matched
   - then per email: sender, subject, date, key points, action items
   - include the `messageId` for each item so the user can reference it for replying

### Notes

- Prefer precise searches: `sender:` + `subject:` + `fromDate:`/`toDate:` beats broad `entire:`.
- Keep `--limit` small (e.g., 5–20) and increase only when necessary.

## Task 2: Reply to a specific email (safe send)

### Workflow (required safety gates)

1. Identify the target email’s `messageId` (typically from `search` output).
2. Draft the reply body in chat (or a local file) and confirm:
   - `fromAddress` (your sending address)
   - `toAddress` (recipient; usually the original sender)
   - `subject`
   - message body
3. Run a dry run first:

`python3 scripts/zoho_mail_cli.py reply --account-id <accountId> --message-id <messageId> --dry-run --content-file /path/to/body.txt`

4. Only after the user explicitly says “send”, run without `--dry-run`.

### Default behavior

- If `--to-address`/`--subject` are omitted, the CLI will try to resolve them from the cached last `search` results (`~/.cache/zoho-mail-handler/last_search.json`). If not found, you must pass them explicitly.

## References

- Search syntax: `references/search_syntax.md`
- API endpoints and payload shapes: `references/api_endpoints.md`
