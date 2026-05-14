---
name: mercari-shop-api-specialist
description: Handle Mercari Shop API work from the Conoha VPS fixed IPv4 path using SSH, the default `~/.ssh/id_ed25519` key, and `curl -4`-forced production access. Use for Mercari GraphQL reads, writes, smoke tests, inventory/order operations, and troubleshooting when the agent must act independently without consulting other docs.
---

# Mercari Shop API Specialist

Use this skill for Mercari Shops API work that must execute from the Conoha VPS and should not depend on other internal docs for SSH, egress, or request shape basics.

## Operating Model

Connection defaults (SSH, egress IP, User-Agent, API base URL) are documented in [references/vps-connection.md](references/vps-connection.md).

- Keep tokens in environment variables only.
- Production and sandbox are separate.
- If sandbox returns `401`, treat it as token or environment mismatch first.
- Start with read-only queries before writes.

## When To Use

Use this skill when the user asks for:

- Mercari API access or troubleshooting
- Production or sandbox GraphQL queries and mutations
- SSH-based VPS execution for Mercari
- Inventory, product, or order operations on Mercari Shops
- Egress/IP verification for Mercari production requests

## Core Workflow

1. Confirm whether the task is production or sandbox.
2. If production is involved, use the VPS SSH path above.
3. Verify the egress IP with `curl -4 -fsS https://ifconfig.me`.
4. Set `MERCARI_API_CLIENT_NAME=Inhouse_ERP`.
5. Set or confirm `MERCARI_API_CLIENT_VERSION`.
6. Run read-only GraphQL first.
7. Only write after the response shape is confirmed.
8. Verify the post-write state.

## Required Request Shapes

### Egress Check

See [references/vps-connection.md](references/vps-connection.md) for the egress verification command and expected IP.

### Production Smoke Test

Run this from the VPS (see [references/vps-connection.md](references/vps-connection.md) for SSH connection details):

```bash
curl -4 -sS \
  -X POST 'https://api.mercari-shops.com/v1/graphql' \
  -H "Authorization: Bearer $MERCARI_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -H "User-Agent: ${MERCARI_API_CLIENT_NAME}/${MERCARI_API_CLIENT_VERSION}" \
  --data '{"query":"query shop { shop { id name businessKind } }"}'
```

### SKU Existence Check

```bash
curl -4 -sS \
  -X POST 'https://api.mercari-shops.com/v1/graphql' \
  -H "Authorization: Bearer $MERCARI_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -H "User-Agent: ${MERCARI_API_CLIENT_NAME}/${MERCARI_API_CLIENT_VERSION}" \
  --data '{"query":"query productVariant($skuCode: String!) { productVariant(by: { skuCode: $skuCode }) { id skuCode } }","variables":{"skuCode":"SKU123"}}'
```

### Product Write Pattern

```bash
curl -4 -sS \
  -X POST 'https://api.mercari-shops.com/v1/graphql' \
  -H "Authorization: Bearer $MERCARI_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -H "User-Agent: ${MERCARI_API_CLIENT_NAME}/${MERCARI_API_CLIENT_VERSION}" \
  --data '{"query":"mutation updateProducts($input: UpdateProductsInput!) { updateProducts(input: $input) { products { id } errors { message } } }","variables":{"input":{}}}'
```

## Workflow Rules

- Check `productVariant(by: { skuCode })` first for each SKU.
- If the SKU exists, skip create for that shop.
- If the SKU does not exist, call `createProduct`.
- Re-check after create even if the mutation returns errors.
- Keep writes idempotent where possible.
- Use the shop-specific token for the target shop.
- Do not mix tokens across shops.
- Keep per-shop execution notes with IDs, status, and errors.

## Safety Rules

- Never hardcode credentials in code.
- Never call Mercari without error handling.
- Handle pagination explicitly for list endpoints.
- Retry network failures with exponential backoff up to 3 times.
- Validate API response status codes and GraphQL errors.
- Do not run production Mercari calls from the local machine.
- If the VPS is correct but the request fails, re-check that IPv4 is forced.

## Error Interpretation

- `401`: auth or token scope issue first
- `404`: environment or source-path mismatch first
- `429`: rate limit, back off and retry
- GraphQL validation error: schema or payload mismatch

## Output Expectations

- Return the key IDs, status, and errors.
- Summarize whether the request succeeded on the fixed-IP path.
- If a write occurred, state the verification result.

## Useful Defaults

- `MERCARI_API_CLIENT_NAME=Inhouse_ERP`
- SSH, egress, and connection defaults: see [references/vps-connection.md](references/vps-connection.md)

