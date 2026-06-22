---
name: rakuten-rms-price-update
description: Change and verify a Rakuten listing's normal purchase price in RMS using deterministic Playwright automation. Use when the user asks to update, revise, or correct a product price in Rakuten RMS by shop ID, product management number, or exact search keyword.
---

# Rakuten RMS Price Update

Update one listing's `通常購入販売価格` in Rakuten RMS. This skill covers only the authenticated RMS operation; it does not calculate prices, read Baserow, choose margins, or update any external system.

## Required input

Prepare a JSON object:

```json
{
  "shopId": "RMS_SHOP_ID",
  "managementNumber": "PRODUCT_MANAGEMENT_NUMBER",
  "searchKeyword": "OPTIONAL_EXACT_KEYWORD",
  "newPrice": 57680,
  "taxIncluded": true,
  "commit": false
}
```

- Prefer `managementNumber`. It enables direct deterministic navigation and avoids searching.
- Use `searchKeyword` only when the management number is unknown.
- `newPrice` is the final positive integer price supplied by the user or an upstream workflow. Do not calculate it here.
- `taxIncluded` defaults to `true`. Unless the user explicitly requests `税別`, select and verify `税込`.
- `commit: false` fills and verifies the form without submitting. Set `commit: true` only when the user has asked to change or update the price.

## Workflow

1. Validate input with `validatePriceUpdateInput` from `scripts/rakuten_rms_price_playwright.mjs`.
2. Claim the user's authenticated Rakuten RMS browser tab and verify the active shop matches `shopId`. Do not reuse a different shop's session.
3. Call `updateRakutenRmsPrice(page, input)` using the browser's Playwright surface.
4. If `managementNumber` is present, navigate directly to:
   `/rms-sku/shops/{shopId}/item/edit/{managementNumber}#tab-1`.
5. Otherwise navigate to the RMS product list, search the exact `searchKeyword`, and require one unambiguous product result. Extract and verify the product management number before opening its `編集` link. Never select by row position alone.
6. Open the `販売・価格` tab and locate the input immediately associated with `通常購入販売価格`. Do not use a generic text-field index.
7. Record the old price, fill `newPrice`, and read it back from the DOM. Set tax treatment to `税込` by default (`税別` only when explicitly requested), verify the selected radio state, and confirm the product management number matches the intended listing.
8. With `commit: false`, return `{status: "ready"}` and stop before `更新する`.
9. With `commit: true`, click `更新する` once.
10. Verify all completion signals:
    - URL ends with `/item/edit/{managementNumber}/complete`;
    - heading is `商品編集完了`;
    - text includes `商品情報の編集が完了しました。`;
    - the completion page displays the expected management number.
11. Perform read-after-write verification: click `商品情報を編集`, reopen `販売・価格`, and assert `通常購入販売価格` equals `newPrice` and the tax treatment remains `税込` by default.
12. Return the management number, old price, new price, completion evidence, and verification result. Close or release only tabs opened for this job.

## Playwright policy

- Use `scripts/rakuten_rms_price_playwright.mjs` for navigation, selectors, write, and verification.
- Prefer direct RMS URLs, visible Japanese labels, URL assertions, and form relationships documented in [references/dom-map.md](references/dom-map.md).
- Do not use recorded coordinates, accessibility-tree element numbers, or blind nth-field selection.
- If one locator fails, inspect a fresh DOM snapshot and repair that locator locally. Do not switch the whole task to Computer Use.
- Use Computer Use only if a specific RMS control cannot be operated with Playwright after DOM inspection.
- Do not inspect or automate Baserow, spreadsheets, pricing calculations, public product pages, or other marketplace operations under this skill.

## Safety and failures

- A request to change/update the price authorizes the RMS submission. A request to inspect, prepare, or preview does not.
- Stop if the shop, product, or management number does not match.
- Stop on ambiguous search results.
- Stop if RMS shows validation errors or disables `更新する`.
- After submission, never click `更新する` again merely because verification is slow. Inspect the completion state first.
- If read-after-write verification differs, report both values and leave the job incomplete.
- Hand CAPTCHA, login, OTP, and account-security prompts to the user.

## Example triggers

- "Change the Rakuten RMS price for shed-1428 to ¥57,680."
- "Update this Rakuten listing price in RMS."
- "Search this RMS item code and correct its normal purchase price."
- "Prepare the Rakuten price change but don't submit it."
