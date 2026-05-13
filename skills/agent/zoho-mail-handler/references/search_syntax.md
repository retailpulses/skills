# Zoho Mail `searchKey` quick reference

Zoho Mail’s `GET /api/accounts/{accountId}/messages/search` uses a `searchKey` query parameter.

## Common parameters

- `sender:<email or keyword>`
- `to:<email or keyword>`
- `cc:<email or keyword>`
- `subject:<word or "exact phrase">`
- `entire:<word or "exact phrase">` (anywhere in the email)
- `content:<word or "exact phrase">` (email content)
- `fileName:<word>` (attachment filename)
- `has:attachment`
- `in:<folder name>` (e.g., `in:Inbox`)
- `label:<label name>`
- `fromDate:DD-Mmm-YYYY`
- `toDate:DD-Mmm-YYYY`
- `inclspamtrash:true`

## Combining terms

Combine multiple terms with `::`:

- `sender:vendor@example.com::subject:"invoice 2026"::fromDate:01-Jan-2026::toDate:21-Apr-2026`
- `entire:refund::in:Inbox::has:attachment`

## Notes

- Wrap phrases in double quotes for exact matches: `subject:"hello world"`.
- If you are in a non‑US Zoho data center, the same syntax still applies; only the API host changes.
