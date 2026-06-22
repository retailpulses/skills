export function validatePriceUpdateInput(raw) {
  const input = structuredClone(raw ?? {});
  if (!/^\d+$/.test(String(input.shopId || ""))) throw new Error("shopId must be a numeric RMS shop ID");
  input.managementNumber = String(input.managementNumber || "").trim();
  input.searchKeyword = String(input.searchKeyword || "").trim();
  if (!input.managementNumber && !input.searchKeyword) throw new Error("managementNumber or searchKeyword is required");
  if (input.managementNumber && !/^[A-Za-z0-9_-]+$/.test(input.managementNumber)) {
    throw new Error("managementNumber contains unsupported characters");
  }
  if (!Number.isSafeInteger(input.newPrice) || input.newPrice <= 0) throw new Error("newPrice must be a positive safe integer");
  if (input.taxIncluded !== undefined && typeof input.taxIncluded !== "boolean") throw new Error("taxIncluded must be boolean");
  input.taxIncluded = input.taxIncluded !== false;
  input.commit = input.commit === true;
  return input;
}

function normalizePrice(value) {
  const digits = String(value ?? "").replace(/[^0-9]/g, "");
  if (!digits) throw new Error(`Could not parse price value: ${value}`);
  return Number(digits);
}

async function priceInput(page) {
  const label = page.getByText("通常購入販売価格", { exact: false }).last();
  await label.waitFor({ state: "visible" });
  const local = label.locator('xpath=ancestor::*[self::div or self::section or self::fieldset][1]//input[not(@type="hidden")][1]');
  if ((await local.count()) === 1) return local;
  const following = label.locator('xpath=following::input[not(@type="hidden")][1]');
  if ((await following.count()) !== 1) throw new Error("Could not uniquely locate 通常購入販売価格 input");
  return following;
}

async function readManagementNumber(page) {
  const marker = page.getByText("商品管理番号（商品URL）", { exact: false }).last();
  await marker.waitFor({ state: "visible" });
  const nearby = marker.locator("xpath=following::*[self::p or self::span or self::div][normalize-space()][1]");
  return (await nearby.innerText()).trim();
}

async function findManagementNumberBySearch(page, input) {
  const listUrl = `https://item.rms.rakuten.co.jp/rms-sku/shops/${input.shopId}/items`;
  await page.goto(listUrl);
  await page.getByRole("heading", { name: /商品一覧/ }).waitFor();
  const search = page.getByPlaceholder("キーワード");
  await search.fill(input.searchKeyword);
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await page.waitForURL((url) => url.searchParams.get("keyword") === input.searchKeyword);

  const exactText = page.getByText(input.searchKeyword, { exact: true });
  const exactCount = await exactText.count();
  if (exactCount !== 1) throw new Error(`Search for ${input.searchKeyword} was ambiguous (${exactCount} exact matches)`);
  const result = exactText.locator('xpath=ancestor::*[self::tr or self::li or @role="row"][1]');
  if ((await result.count()) !== 1) throw new Error("Could not identify the unique RMS result container");
  const edit = result.getByRole("link", { name: "編集", exact: true });
  if ((await edit.count()) !== 1) throw new Error("Could not identify a unique 編集 link for the matched result");
  const href = await edit.getAttribute("href");
  const match = href?.match(/\/item\/edit\/([^/?#]+)/);
  if (!match) throw new Error("Matched RMS result did not expose a management number");
  await edit.click();
  return decodeURIComponent(match[1]);
}

async function openPriceForm(page, input) {
  let managementNumber = input.managementNumber;
  if (managementNumber) {
    await page.goto(`https://item.rms.rakuten.co.jp/rms-sku/shops/${input.shopId}/item/edit/${encodeURIComponent(managementNumber)}#tab-1`);
  } else {
    managementNumber = await findManagementNumberBySearch(page, input);
  }
  await page.getByRole("heading", { name: /商品編集/ }).waitFor();
  const priceTab = page.getByRole("link", { name: "販売・価格", exact: true });
  await priceTab.click();
  await page.waitForURL((url) => url.hash === "#tab-1");
  const displayedManagementNumber = await readManagementNumber(page);
  if (displayedManagementNumber !== managementNumber) {
    throw new Error(`Product mismatch: expected ${managementNumber}, found ${displayedManagementNumber}`);
  }
  return managementNumber;
}

export async function updateRakutenRmsPrice(page, rawInput) {
  const input = validatePriceUpdateInput(rawInput);
  const current = new URL(page.url());
  if (!current.hostname.endsWith("rakuten.co.jp")) throw new Error("Use an authenticated Rakuten RMS browser tab");
  if (current.pathname.includes("/shops/") && !current.pathname.includes(`/shops/${input.shopId}/`)) {
    throw new Error("The active RMS tab belongs to a different shop");
  }

  const managementNumber = await openPriceForm(page, input);
  const field = await priceInput(page);
  const oldPrice = normalizePrice(await field.inputValue());
  await field.fill(String(input.newPrice));
  const preparedPrice = normalizePrice(await field.inputValue());
  if (preparedPrice !== input.newPrice) throw new Error(`Price field mismatch: expected ${input.newPrice}, got ${preparedPrice}`);

  const taxLabel = input.taxIncluded ? "税込" : "税別";
  const taxRadio = page.getByRole("radio", { name: taxLabel, exact: true });
  if ((await taxRadio.count()) !== 1) throw new Error(`Could not uniquely locate tax treatment: ${taxLabel}`);
  await taxRadio.check();
  if (!(await taxRadio.isChecked())) throw new Error(`Tax treatment verification failed: ${taxLabel}`);

  const update = page.getByRole("button", { name: "更新する", exact: true });
  if (!(await update.isEnabled())) throw new Error("RMS 更新する button is disabled");
  const result = { managementNumber, oldPrice, newPrice: input.newPrice, taxIncluded: input.taxIncluded, taxLabel };
  if (!input.commit) return { status: "ready", ...result };

  await update.click();
  await page.waitForURL(new RegExp(`/item/edit/${managementNumber}/complete$`));
  await page.getByRole("heading", { name: "商品編集完了", exact: true }).waitFor();
  await page.getByText("商品情報の編集が完了しました。", { exact: false }).waitFor();
  await page.getByText(managementNumber, { exact: true }).waitFor();

  await page.getByRole("button", { name: "商品情報を編集", exact: true }).click();
  await page.waitForURL(new RegExp(`/item/edit/${managementNumber}(?:#.*)?$`));
  await page.getByRole("link", { name: "販売・価格", exact: true }).click();
  await page.waitForURL((url) => url.hash === "#tab-1");
  const savedPrice = normalizePrice(await (await priceInput(page)).inputValue());
  if (savedPrice !== input.newPrice) throw new Error(`Read-after-write mismatch: expected ${input.newPrice}, got ${savedPrice}`);
  const savedTaxRadio = page.getByRole("radio", { name: taxLabel, exact: true });
  if (!(await savedTaxRadio.isChecked())) throw new Error(`Read-after-write tax mismatch: expected ${taxLabel}`);
  return { status: "updated", ...result, savedPrice, savedTaxLabel: taxLabel, verified: true, url: page.url() };
}
