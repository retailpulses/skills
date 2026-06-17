# Zoho Mail endpoints used by this skill

Base API (default): `https://mail.zoho.com/api`

Auth header for API calls:

- `Authorization: Zoho-oauthtoken <access_token>`

## OAuth (access token refresh)

Base (default): `https://accounts.zoho.com`

- `POST {accounts_base}/oauth/v2/token`
  - Body (x-www-form-urlencoded):
    - `refresh_token=<...>`
    - `grant_type=refresh_token`
    - `client_id=<...>`
    - `client_secret=<...>`

## Account discovery

- `GET /accounts`
  - Use to discover `accountId` for subsequent calls.

## Folder discovery

- `GET /accounts/{accountId}/folders`
  - Use to discover `folderId` when fetching message content.

## Search

- `GET /accounts/{accountId}/messages/search?searchKey=...`
  - Optional query params: `start`, `limit`, `receivedTime`, `includeto`

## Content fetch (HTML)

- `GET /accounts/{accountId}/folders/{folderId}/messages/{messageId}/content`
  - Response includes `data.content` (HTML string).

## Reply (send)

- `POST /accounts/{accountId}/messages/{messageId}`
  - JSON body (minimum):
    - `fromAddress`
    - `toAddress`
    - `subject`
    - `content`
    - `action`: use `reply`
  - Optional:
    - `ccAddress`, `bccAddress`
    - `mailFormat`: `html` or `plaintext`
    - `encoding` (default `UTF-8`)
    - `askReceipt`: `yes`/`no`
