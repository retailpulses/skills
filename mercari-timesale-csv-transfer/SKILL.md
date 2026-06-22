---
name: mercari-timesale-csv-transfer
description: Download generated Mercari Shops time-sale CSV files and upload prepared time-sale CSV files through the authenticated seller backend using Playwright. Use when the user asks to download, export, upload, or import a Mercari time-sale CSV without creating prices or applying the time-sale settings.
---

# Mercari Time-sale CSV Transfer

Handle only CSV transfer in the logged-in Mercari Shops seller backend:

- generate and download an eligible-product time-sale CSV;
- upload an already prepared time-sale CSV;
- report the upload-history state.

Do not edit CSV contents, calculate prices, define sale periods, resume configuration, or apply time-sale settings.

## Requirements

- Use the user's authenticated Chrome or Edge profile for the intended Mercari shop.
- Prefer the Playwright functions in `scripts/mercari_timesale_csv_playwright.mjs`.
- Verify the active shop before navigating or transferring files.
- A request to upload a specific CSV authorizes transmitting that file to the specified Mercari shop. Otherwise, stop before `setInputFiles`.

## Direct routes

Parameterize `{shopId}`:

- Unconfigured/registration CSV: `/seller/shops/{shopId}/dualprice/products/download`
- Configured/update CSV: `/seller/shops/{shopId}/dualprice/existing_products/download`
- Upload: `/seller/shops/{shopId}/dualprice/upload`

## Download workflow

1. Collect `shopId`, download kind (`registration` or `existing`), and output directory. Default kind is `registration`.
2. Call `downloadMercariTimesaleCsv(page, input)`.
3. Navigate directly to the matching download route.
4. For registration downloads, leave `過去価格(中央値)のタイムセールを含める` unchecked unless explicitly requested. Do not alter other filters unless the user provides them.
5. Record the newest history row, click `作成` once, and close the creation notice when it appears.
6. Wait for a new first history row and status `完了`. Do not click an older row's download button.
7. Capture the Playwright download event, click `ダウンロード` within that new row, and save the file to the requested directory.
8. Verify the saved file exists, is non-empty, and has a `.csv` extension. Return its absolute path and source kind.

## Upload workflow

1. Collect `shopId` and the absolute path of an existing non-empty `.csv` file.
2. Call `uploadMercariTimesaleCsv(page, input)`.
3. Navigate directly to `/seller/shops/{shopId}/dualprice/upload`.
4. Use Playwright `setInputFiles` on the file input associated with `ファイルを選択`. Do not use the native file picker or Computer Use.
5. Wait until the exact uploaded filename appears as the newest matching history entry.
6. Read and return the row's visible state. Possible observed states include `エラー`, `設定完了`, or a resumable state with `設定を再開する`.
7. Stop after upload/history verification. Never click `設定を再開する`; that applies or continues time-sale configuration and is outside this skill.
8. If the row reports `エラー`, report it and the availability of its error-file `ダウンロード` button. Do not modify and re-upload the CSV automatically.

## Playwright policy

- Use semantic links/buttons, direct URLs, exact filenames, history-row scoping, download events, and `setInputFiles`.
- Never use recorded coordinates, global “first download” selection without proving it belongs to the newly created row, or native file-dialog automation.
- Inspect a fresh DOM snapshot only when one stable locator fails; repair that locator locally.
- Use Computer Use only when Playwright cannot access a specific seller-backend control after DOM inspection.
- See [references/dom-map.md](references/dom-map.md) for recorded labels and route structure.

## Guardrails

- Never generate or change the business contents of a CSV.
- Never upload to a shop whose ID/profile has not been verified.
- Never upload non-CSV, missing, or empty files.
- Never click `設定を再開する` or otherwise apply the uploaded settings.
- Never assume upload success merely because the file picker closed; verify the exact filename in history.
- Never retry an upload blindly. Inspect whether the filename already exists in history first.
- Hand login, CAPTCHA, OTP, and account-security prompts to the user.

## Example triggers

- "Download the Mercari time-sale registration CSV."
- "Export the configured time-sale products CSV from Shop1."
- "Upload this prepared time-sale CSV to Mercari."
- "Check whether the Mercari time-sale CSV upload reached the history table."

