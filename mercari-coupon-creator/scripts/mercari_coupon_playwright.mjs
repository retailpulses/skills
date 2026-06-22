const JST_OFFSET = "+09:00";
const MAX_PERIOD_MS = 30 * 24 * 60 * 60 * 1000;

function positiveInteger(value, name) {
  if (!Number.isInteger(value) || value <= 0) throw new Error(`${name} must be a positive integer`);
}

export function validateCouponInput(raw) {
  const input = structuredClone(raw ?? {});
  if (!/^[A-Za-z0-9_-]+$/.test(input.shopId || "")) throw new Error("shopId is required");
  if (!Array.isArray(input.productCodes) || input.productCodes.length === 0) throw new Error("productCodes must be a non-empty array");
  input.productCodes = input.productCodes.map((code) => String(code).trim());
  if (input.productCodes.some((code) => !code)) throw new Error("productCodes cannot contain blanks");
  if (new Set(input.productCodes).size !== input.productCodes.length) throw new Error("productCodes contains duplicates");
  if (input.productCodes.length > 1000) throw new Error("Mercari allows at most 1000 selected products");
  if (!["amount", "percent"].includes(input.discountType)) throw new Error("discountType must be amount or percent");
  positiveInteger(input.discountValue, "discountValue");
  positiveInteger(input.issueCount, "issueCount");
  if (typeof input.singleUsePerBuyer !== "boolean") throw new Error("singleUsePerBuyer must be boolean");
  for (const name of ["startAt", "endAt"]) {
    if (!String(input[name] || "").endsWith(JST_OFFSET)) throw new Error(`${name} must include the +09:00 JST offset`);
  }
  const start = new Date(input.startAt);
  const end = new Date(input.endAt);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) throw new Error("startAt and endAt must be valid ISO date-times");
  if (end <= start) throw new Error("endAt must be after startAt");
  if (end - start > MAX_PERIOD_MS) throw new Error("coupon period cannot exceed 30 days");
  input.commit = input.commit === true;
  return input;
}

function dateAndTime(iso) {
  return { date: iso.slice(0, 10), time: iso.slice(11, 16) };
}

async function selectFollowingSelect(page, labelText, optionText) {
  const label = page.getByText(labelText, { exact: true }).last();
  const select = label.locator("xpath=following::select[1]");
  await select.selectOption({ label: optionText });
  return select;
}

async function selectProduct(page, productCode) {
  const search = page.getByPlaceholder("商品管理コード（前方一致）、商品名検索");
  await search.fill(productCode);
  await search.press("Enter");
  await page.waitForURL((url) => url.searchParams.get("keyword") === productCode);

  const checkboxes = page.locator('input[type="checkbox"]:visible');
  await checkboxes.first().waitFor({ state: "visible" });
  const count = await checkboxes.count();
  if (count === 1) {
    await checkboxes.first().check();
    return;
  }

  const exact = page.locator('input[type="checkbox"]:visible').filter({ has: page.getByText(productCode, { exact: true }) });
  if ((await exact.count()) !== 1) {
    throw new Error(`Ambiguous product search for ${productCode}: ${count} selectable results`);
  }
  await exact.check();
}

async function assertValue(locator, expected, name) {
  const actual = await locator.inputValue();
  if (actual !== expected) throw new Error(`${name} mismatch: expected ${expected}, got ${actual}`);
}

export async function createMercariCoupon(page, rawInput) {
  const input = validateCouponInput(rawInput);
  const base = `https://mercari-shops.com/seller/shops/${input.shopId}`;
  const currentUrl = new URL(page.url());
  if (currentUrl.hostname !== "mercari-shops.com" || (!currentUrl.pathname.includes(`/seller/shops/${input.shopId}/`) && currentUrl.pathname !== "/")) {
    throw new Error("The authenticated browser tab does not match the requested Mercari shop");
  }

  await page.goto(`${base}/coupon/create`);
  await page.getByRole("heading", { name: "クーポンの設定" }).waitFor();
  await selectFollowingSelect(page, "クーポンの使用範囲", "商品単位");
  await page.getByRole("button", { name: "商品を追加する" }).click();
  await page.getByText("商品を選択", { exact: true }).click();
  await page.waitForURL(`${base}/coupon/create/products**`);

  for (const productCode of input.productCodes) await selectProduct(page, productCode);
  await page.getByRole("button", { name: "選択した商品を追加する" }).click();
  await page.waitForURL(`${base}/coupon/create`);
  await page.getByText(`${input.productCodes.length}点の商品を追加済み`, { exact: false }).waitFor();

  const discountLabel = input.discountType === "amount" ? "割引金額(￥〇〇割引)" : "割引率(〇〇%OFF)";
  await selectFollowingSelect(page, "割引内容", discountLabel);
  const discount = page.getByPlaceholder("￥0");
  const issueCount = page.getByPlaceholder("0枚");
  await discount.fill(String(input.discountValue));
  await issueCount.fill(String(input.issueCount));

  const singleUse = page.getByText("1人1回制限の設定", { exact: true }).locator('xpath=following::input[@type="checkbox"][1]');
  if (input.singleUsePerBuyer) await singleUse.check();
  else await singleUse.uncheck();

  const start = dateAndTime(input.startAt);
  const end = dateAndTime(input.endAt);
  const dates = page.locator('input[type="date"]');
  if ((await dates.count()) !== 2) throw new Error("Expected exactly two coupon date inputs");
  await dates.nth(0).fill(start.date);
  await dates.nth(1).fill(end.date);
  const startTime = dates.nth(0).locator("xpath=following::select[1]");
  const endTime = dates.nth(1).locator("xpath=following::select[1]");
  await startTime.selectOption({ label: start.time });
  await endTime.selectOption({ label: end.time });

  await assertValue(discount, String(input.discountValue), "discountValue");
  await assertValue(issueCount, String(input.issueCount), "issueCount");
  await assertValue(dates.nth(0), start.date, "start date");
  await assertValue(dates.nth(1), end.date, "end date");
  if ((await startTime.inputValue()) !== start.time || (await endTime.inputValue()) !== end.time) throw new Error("Coupon time verification failed");
  if ((await singleUse.isChecked()) !== input.singleUsePerBuyer) throw new Error("singleUsePerBuyer verification failed");

  const submit = page.getByRole("button", { name: "クーポンを設定する" });
  if (!(await submit.isEnabled())) throw new Error("Coupon form is not ready to submit");
  const preview = { ...input, discountLabel, start, end, verified: true };
  if (!input.commit) return { status: "ready", preview };

  await submit.click();
  const dialog = page.getByText("クーポンを設定しますか？", { exact: true });
  await dialog.waitFor();
  await page.getByRole("button", { name: "設定する", exact: true }).click();
  await page.waitForURL((url) => url.searchParams.get("state") === "STATE_NOT_STARTED" && url.searchParams.get("scope") === "SCOPE_PRODUCT");
  await page.getByText("クーポンの発行が完了しました", { exact: true }).waitFor();
  await page.getByText(new RegExp(`残り枚数:\\s*${input.issueCount}/${input.issueCount}枚`)).waitFor();
  return { status: "created", preview, url: page.url() };
}

