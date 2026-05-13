---
name: zoho-mail-access
description: Standalone Zoho Mail access skill for refreshing local OAuth credentials, searching messages by subject or keywords, and capturing matched message contents from this workspace.
---

# Zoho Mail Access

Use this skill when you need occasional access to the Zoho Mail account in this workspace, especially to find messages by subject or keywords and capture their contents into a local deliverable.

## Operating Rules

- Use the local Zoho setup already present in this repo.
- Do not ask the user for OAuth details if the workspace already has them.
- Never print secrets or raw tokens.
- Prefer the helper script in this skill over ad hoc API calls.

## Credential Sources

Load credentials in this order:

1. `dev.env` at the repo root
2. `variables and secrets.txt` in the repo root, if present
3. Current process environment

Required keys:

- `ZOHO_CLIENT_ID`
- `ZOHO_CLIENT_SECRET`
- `ZOHO_REFRESH_TOKEN`

Optional keys:

- `ZOHO_ACCOUNT_ID`
- `ACCOUNTS_DOMAIN` or `ZOHO_ACCOUNTS_DOMAIN`
- `ZOHO_INBOX_FOLDER_ID`

If a required key is missing, stop and report the missing names.

## Workflow

1. Refresh a Zoho access token with the local refresh token.
2. Resolve `ZOHO_ACCOUNT_ID` if it is not already present.
3. List Zoho messages from the inbox or the selected folder.
4. Filter messages by subject and keywords.
5. Fetch full message content for matches.
6. Save a capture bundle under `deliverables/zoho-mail/` unless the caller supplies another output directory.

## Matching Rules

- Subject matching is case-insensitive.
- Keywords are case-insensitive.
- Default keyword mode is `any`.
- Match against subject first, then snippet/body when content is fetched.
- Sort final matches by received time descending when possible.

## Helper Script

Use [scripts/zoho_mail_access.js](scripts/zoho_mail_access.js) for direct access.

Typical capture command:

```bash
node scripts/zoho_mail_access.js capture --subject "order update" --keywords "payment,refund" --capture-dir "./deliverables/zoho-mail/order-update"
```

Common outputs:

- `capture.json` for machine use
- `capture.md` for quick review
- one folder per capture run

