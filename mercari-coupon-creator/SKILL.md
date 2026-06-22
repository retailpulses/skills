---
name: mercari-coupon-creator
description: Create product-scoped Mercari Shops coupons with a deterministic Playwright workflow using SKU search, discount and quantity settings, scheduled dates, confirmation, and completion verification. Use when the user asks to create, schedule, issue, or configure a Mercari coupon for one or more products.
---

# Mercari Coupon Creator

Create Mercari Shops product coupons from structured input. Prefer the reusable Playwright module over AI-guided clicking or Computer Use.

## Requirements

- Use the user's authenticated Chrome or Edge profile for the intended Mercari shop.
- Use the browser's Playwright surface and `scripts/mercari_coupon_playwright.mjs`.
- Collect these inputs before creating a coupon: shop ID or verified shop profile, exact product management code(s), discount type and value, issue count, one-use-per-buyer setting, and JST start/end date-times.
- Treat the final `設定する` action as an external side effect. A request to create or issue the coupon authorizes it; otherwise prepare a dry-run and stop before submission.

## Structured input

Create a JSON object matching this example:

```json
{
  "shopId": "SHOP_ID",
  "productCodes": ["ITEM_CODE"],
  "discountType": "amount",
  "discountValue": 200,
  "issueCount": 10,
  "singleUsePerBuyer": false,
  "startAt": "2026-06-21T08:00:00+09:00",
  "endAt": "2026-06-25T23:00:00+09:00",
  "commit": false
}
```

`discountType` is `amount` for `割引金額(￥〇〇割引)` or `percent` for `割引率(〇〇%OFF)`. Dates must carry the `+09:00` JST offset.

## Workflow

1. Run `validateCouponInput(input)` from `scripts/mercari_coupon_playwright.mjs`. Reject missing fields, duplicate product codes, non-positive numeric values, a non-JST offset, an end before the start, or a period longer than 30 days.
2. Claim the already authenticated tab for the intended shop. Verify that its profile and URL correspond to `input.shopId`; never reuse another shop's session implicitly.
3. Pass the Playwright `page` and the validated input to `createMercariCoupon(page, input)`.
4. The script navigates directly to `/seller/shops/{shopId}/coupon/create`, selects `商品単位`, and opens `商品を選択`.
5. For each product code, the script searches the exact code and selects a single deterministic result. It must stop if no result exists or multiple results remain and the exact code cannot be tied to one result. Never choose a product by visual similarity or list position alone.
6. The script adds the selected products, chooses the discount type, fills the discount value and issue count, sets the one-use checkbox, and fills both JST date/time pairs.
7. Before submission, verify from the DOM that:
   - the page reports the expected number of products added;
   - the selected discount type and displayed value match the input;
   - issue count and checkbox state match;
   - both date and time controls match;
   - the `クーポンを設定する` button is enabled and no validation error is visible.
8. With `commit: false`, return the verified preview and do not click either submission button.
9. With `commit: true` and user authorization, click `クーポンを設定する`, verify the `クーポンを設定しますか？` dialog, then click its `設定する` button once.
10. Verify success using both authoritative signals: URL state `state=STATE_NOT_STARTED&scope=SCOPE_PRODUCT` and text `クーポンの発行が完了しました`. Confirm the new coupon card matches discount, period, issue count, and product scope.
11. Close or release only the browser tabs opened for this job after verification.

## Determinism rules

- Prefer `getByRole`, `getByText`, placeholders, native input types, and URL assertions. Do not use recorded coordinates or accessibility-tree element numbers.
- Use exact visible Japanese labels from [references/dom-map.md](references/dom-map.md).
- Use the input's product code as the search key. Do not infer products from names.
- Use native `selectOption`, `fill`, `check`, and `uncheck` where possible.
- Take one fresh DOM snapshot only when a recorded locator fails. Repair the selector locally; do not switch the whole workflow to Computer Use.
- Computer Use is a last resort for a control that Playwright cannot operate after DOM inspection.
- Never retry the final confirmation click after navigation or a success signal; verify the result first to avoid duplicate coupons.

## Failure handling

- Authentication or wrong shop: stop before filling.
- Ambiguous product search: stop and report the product code.
- Page validation error: report its visible text and do not submit.
- No success signal after the final click: inspect the current URL, dialog, and coupon list before considering any retry.
- CAPTCHA or account-security prompt: hand control to the user.

## Example triggers

- "Create a ¥300 Mercari coupon for this SKU."
- "Schedule product coupons for Shop2 next weekend."
- "Issue ten 5%-off coupons for these Mercari item codes."
- "Prepare a Mercari coupon and stop before submitting."

