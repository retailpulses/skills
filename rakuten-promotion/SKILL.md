---
name: rakuten-promotion
description: >
  Create and manage Rakuten RMS coupons and thanks coupons via the Rakuten Promotion API.
  Use this skill when you need to issue, update, delete, or search for coupons on Rakuten Ichiba,
  set up thanks (auto-grant) coupons with purchase conditions, run seasonal promotion campaigns,
  or bulk-manage discount strategies. Wraps the Rakuten RMS CouponAPI (/es/1.0/coupon/*) and
  ThanksCouponAPI (/es/1.0/thankscoupon*). Credentials from RAKUTEN_SERVICE_SECRET +
  RAKUTEN_LICENSE_KEY env vars.
---

# Rakuten Promotion API

API-first TypeScript client for Rakuten RMS Coupon & Thanks Coupon management.

## When to Use

- Issuing new discount coupons (percentage, fixed amount, free shipping)
- Updating or deleting existing coupons
- Searching for active/expired coupons by name, date range, or item URL
- Setting up thanks coupons (auto-granted to customers meeting purchase criteria)
- Stopping thanks coupon distribution early
- Bulk campaign management (issue, audit, deactivate across product lines)
- Any Rakuten promotion operation that requires programmatic control

## Quick Start

```ts
import { createPromotionClient } from "./scripts/src/index.ts";

const client = createPromotionClient({
  serviceSecret: process.env.RAKUTEN_SERVICE_SECRET!,
  licenseKey: process.env.RAKUTEN_LICENSE_KEY!,
});

// Issue a 10% off entire-order coupon
const result = await client.coupon.issue({
  couponName: "サマーセール10%オフ",
  couponCaption: "全品10%割引",
  couponStartDate: "2026-07-01T00:00:00+09:00",
  couponEndDate: "2026-07-31T23:59:59+09:00",
  couponIssueCount: 1000,
  itemType: 4,      // entire order
  discountType: 2,  // percentage
  discountFactor: 10,
  combineFlag: 0,
  displayFlag: 1,
});
console.log(`Issued: ${result.couponCode}`);
```

## Credential Setup

Required env vars — never hardcode, never commit to git:

| Variable | Source | Notes |
|----------|--------|-------|
| `RAKUTEN_SERVICE_SECRET` | RMS WEB API Service settings → App Registration → Details | Permanent |
| `RAKUTEN_LICENSE_KEY` | Same location → "Change verification license key" | **Expires every 90 days** |

To obtain: Login to https://mainmenu.rms.rakuten.co.jp/rms → "Information and Services for stores" → "5 WEB API Service" → "App Registration" → "Details". Ensure "CouponAPI" is set to "In Use" under "Edit Available Functions".

**⚠️ License key expiry**: Keys expire every 90 days. Check before running promotion operations — use `LicenseManagementAPI` or test a search call.

## API Surface

### Coupon API (standard customer-facing coupons)

```ts
// Create
client.coupon.issue(input: CouponToIssue): Promise<IssuedCoupon>

// Update (input must include couponCode)
client.coupon.update(coupon: CouponToIssue & { couponCode: string }): Promise<void>

// Delete
client.coupon.delete({ couponCode: string }): Promise<void>

// Get single coupon by code
client.coupon.get(couponCode: string): Promise<Coupon | null>

// Search with filters
client.coupon.search(condition?: CouponSearchCondition): Promise<CouponSearchResponse>

// Auto-paginated search — iterate all results
for await (const page of client.coupon.searchAll(condition)) {
  for (const coupon of page.coupons) { /* ... */ }
}
```

### Thanks Coupon API (auto-grant customer loyalty coupons)

```ts
// Create
client.thanksCoupon.issue(input: ThanksCouponToIssue): Promise<number>

// Update
client.thanksCoupon.update(id: number, input: Partial<ThanksCouponToIssue>): Promise<number>

// Stop distribution early
client.thanksCoupon.stop(id: number): Promise<number>

// Get by ID
client.thanksCoupon.get(id: number): Promise<ThanksCoupon | null>

// Search with filters
client.thanksCoupon.search(condition?: SearchThanksCouponCondition): Promise<ThanksCouponSearchResponse | null>

// Auto-paginated search
for await (const page of client.thanksCoupon.searchAll(condition)) {
  for (const c of page.thanksCoupons) { /* ... */ }
}
```

## Key DTOs

### CouponToIssue

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `couponName` | string | ✅ | Max 50 chars |
| `couponCaption` | string | ✅ | Max 30 chars |
| `couponStartDate` | string | ✅ | ISO 8601 with JST offset |
| `couponEndDate` | string | ✅ | ISO 8601 with JST offset |
| `couponIssueCount` | number | ✅ | ≥ 1 |
| `itemType` | number | ✅ | 1=single, 3=multiple, 4=order, 5=free shipping |
| `discountType` | number | ✅ | 1=fixed(yen), 2=percentage, 4=free shipping |
| `discountFactor` | number | ✅ | Amount in yen (type=1) or percentage 1-99 (type=2) |
| `combineFlag` | 0\|1 | ✅ | 0=no combine, 1=can combine |
| `couponImageUrl` | string | — | Image URL |
| `memberMaxCount` | number | — | Max uses per member (default 1) |
| `displayFlag` | 0\|1 | — | 0=hidden, 1=visible (default 1) |
| `items` | CouponItem[] | — | Required when itemType=1 or 3. Max 3000. |
| `otherConditions` | OtherCondition[] | — | Device/sales/amount/quantity restrictions |
| `rankCondition` | RankCondition | — | Gender/age/prefecture/rank targeting |

### ThanksCouponToIssue

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `couponName` | string | ✅ | Max 50 chars |
| `couponCaption` | string | ✅ | Max 30 chars |
| `discountType` | number | ✅ | 1=fixed, 2=percentage, 4=free shipping |
| `discountFactor` | number | ✅ | Same as coupon |
| `couponTerm` | number | ✅ | Validity in days from grant date |
| `memberAvailMaxCount` | number | ✅ | ≥ 1 |
| `combineFlag` | 0\|1 | ✅ | 0=no combine, 1=can combine |
| `thanksAutoGetConditions` | AutoGetCondition[] | ✅ | Must include totalPrice + grantTerm |
| `couponUnavailableTerm` | number | — | Days before coupon usable |
| `thanksOtherConditions` | OtherCondition[] | — | Usage restrictions |

### CouponSearchCondition

| Field | Type | Description |
|-------|------|-------------|
| `couponName` | string | Partial name match |
| `couponCode` | string | Exact coupon code |
| `itemUrl` | string | Filter by target item |
| `couponStartDate` | string | Active on/after |
| `couponEndDate` | string | Active on/before |
| `hits` | number | Per page (max ~200) |
| `page` | number | 1-indexed |

## Error Handling

All API errors throw `RakutenPromotionError`:

```ts
try {
  await client.coupon.issue({...});
} catch (err) {
  if (err instanceof RakutenPromotionError) {
    console.error(err.errorSummary);  // "[COUPON-001] Name too long; [COUPON-003] Invalid date"
    console.error(err.httpStatus);    // 400
    console.error(err.retryable);     // false (4xx not retryable)
    console.error(err.errors);        // RakutenApiError[]
  }
}
```

**Retryable errors**: 429 (rate limit), 5xx (server), network errors. Not retryable: other 4xx.

**404 on thanks coupon search**: Returns `null` (not an error — this is documented RMS behavior).

## Rate Limiting & Retry

Default: **1 request/second** with exponential backoff on retryable failures.

```ts
const client = createPromotionClient({
  serviceSecret: "...",
  licenseKey: "...",
  rateLimitDelayMs: 2000,  // 1 req / 2 sec (conservative)
  retryConfig: {
    maxAttempts: 5,        // more retries
    baseBackoffMs: 2000,   // start with 2s
    maxBackoffMs: 60_000,  // cap at 60s
  },
});
```

## Dry-Run Mode

Test without sending real requests:

```ts
const client = createPromotionClient({
  serviceSecret: "test",
  licenseKey: "test",
  dryRun: true,
});
// All calls log to console and return fake success responses
```

## Validation

Built-in validators for input checking:

```ts
import { validateCouponToIssue, validateThanksCouponToIssue } from "./scripts/src/index.ts";

const errors = validateCouponToIssue(myCoupon);
if (errors.length > 0) {
  for (const e of errors) console.error(e.message);
}
```

## Repository/Adapter Pattern

Per project architecture (CLAUDE.md), wrap this client:

```ts
// adapters/rakuten-promotion.ts — vendor API calls live ONLY here
import { createPromotionClient } from "../lib/rakuten-promotion-api";
export function createRakutenPromotionAdapter(env: Env) {
  const client = createPromotionClient({
    serviceSecret: env.RAKUTEN_SERVICE_SECRET,
    licenseKey: env.RAKUTEN_LICENSE_KEY,
  });
  return {
    issueCoupon: (p) => client.coupon.issue(p),
    searchCoupons: (c) => client.coupon.search(c),
    deleteCoupon: (code) => client.coupon.delete({ couponCode: code }),
    // ... thanks coupon methods
  };
}

// repositories/promotion.ts — business logic layer
import { createRakutenPromotionAdapter } from "../adapters/rakuten-promotion";
export function createPromotionRepo(env: Env) {
  const adapter = createRakutenPromotionAdapter(env);
  return {
    async runSeasonalCampaign(products, discountPct, startDate, endDate) {
      // Business logic: validate, check for existing coupons, create or extend
    },
  };
}
```

## Testing

The client ships with Vitest tests. Run:

```bash
cd scripts && npm install && npm test
```

Without a sandbox environment, use:
- **Fixture-based tests**: Stored XML responses in `__tests__/fixtures/`
- **Dry-run mode**: `createPromotionClient({ ..., dryRun: true })` logs requests
- **Search with `hits: 1`**: Safe live smoke test (read-only, 1 result)

## Reference Docs

- `references/coupon-api-contract.md` — Wire-level XML schema for all coupon endpoints
- `references/thanks-coupon-contract.md` — Wire-level XML schema for thanks coupon endpoints

## Constraints & Gotchas

1. **License key 90-day expiry** — check before operations
2. **No sandbox** — test with dry-run mode and fixture data
3. **JST timezone** — all dates must include `+09:00` offset
4. **XML field ordering** — the client controls element order per reference library
5. **Max 3000 items per coupon** — enforced by validator
6. **Thanks coupon search returns 404 on empty** — handled as `null`, not error
7. **1-2 hour propagation delay** after enabling new API permissions in RMS settings
8. **No rate limit documentation from Rakuten** — default 1 req/sec is conservative

## Port Source

Ported from JakeJP/Rakuten.RMS.Api (MIT license, v3.0.1, updated Dec 2025).
Authentication, endpoints, DTOs, validation rules, and error parsing adapted from .NET to TypeScript.
Retry and rate-limiting are new additions (not present in .NET reference).
