import fs from "node:fs";
import path from "node:path";

const BASE = "https://mercari-shops.com/seller/shops";

function validShopId(value) {
  return /^[A-Za-z0-9_-]+$/.test(String(value || ""));
}

export function validateDownloadInput(raw) {
  const input = structuredClone(raw ?? {});
  if (!validShopId(input.shopId)) throw new Error("shopId is required");
  input.kind = input.kind || "registration";
  if (!["registration", "existing"].includes(input.kind)) throw new Error("kind must be registration or existing");
  if (!input.outputDir || !path.isAbsolute(input.outputDir)) throw new Error("outputDir must be an absolute path");
  input.includeMedianPrice = input.includeMedianPrice === true;
  return input;
}

export function validateUploadInput(raw) {
  const input = structuredClone(raw ?? {});
  if (!validShopId(input.shopId)) throw new Error("shopId is required");
  if (!input.csvPath || !path.isAbsolute(input.csvPath)) throw new Error("csvPath must be an absolute path");
  if (path.extname(input.csvPath).toLowerCase() !== ".csv") throw new Error("csvPath must end in .csv");
  if (!fs.existsSync(input.csvPath)) throw new Error("CSV file does not exist");
  if (fs.statSync(input.csvPath).size === 0) throw new Error("CSV file is empty");
  return input;
}

function verifyShopContext(page, shopId) {
  const current = new URL(page.url());
  if (current.hostname !== "mercari-shops.com") throw new Error("Use an authenticated Mercari Shops browser tab");
  const match = current.pathname.match(/\/seller\/shops\/([^/]+)/);
  if (match && match[1] !== shopId) throw new Error("The active Mercari tab belongs to a different shop");
}

async function waitUntil(check, message, timeoutMs = 120000, intervalMs = 1000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await check();
    if (result) return result;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(message);
}

function historyRows(page) {
  return page.locator('tr').filter({ has: page.getByRole("button", { name: "ダウンロード", exact: true }) });
}

export async function downloadMercariTimesaleCsv(page, rawInput) {
  const input = validateDownloadInput(rawInput);
  verifyShopContext(page, input.shopId);
  const route = input.kind === "registration" ? "dualprice/products/download" : "dualprice/existing_products/download";
  await page.goto(`${BASE}/${input.shopId}/${route}`);
  await page.getByRole("heading", { name: /商品データ（CSV）を作成する/ }).waitFor();

  if (input.kind === "registration") {
    const median = page.getByRole("checkbox", { name: /過去価格\(中央値\)のタイムセールを含める/ });
    if ((await median.count()) === 1) {
      if (input.includeMedianPrice) await median.check();
      else await median.uncheck();
    }
  }

  const rowsBefore = historyRows(page);
  const firstBefore = (await rowsBefore.count()) ? await rowsBefore.first().innerText() : "";
  await page.getByRole("button", { name: "作成", exact: true }).click();
  const close = page.getByRole("button", { name: "閉じる", exact: true });
  if (await close.isVisible().catch(() => false)) await close.click();

  const newRow = await waitUntil(async () => {
    const rows = historyRows(page);
    if (!(await rows.count())) return null;
    const first = rows.first();
    const text = await first.innerText();
    return text !== firstBefore && /完了/.test(text) ? first : null;
  }, "A newly completed CSV history row did not appear");

  const downloadPromise = page.waitForEvent("download");
  await newRow.getByRole("button", { name: "ダウンロード", exact: true }).click();
  const download = await downloadPromise;
  const suggested = download.suggestedFilename();
  if (path.extname(suggested).toLowerCase() !== ".csv") throw new Error(`Unexpected downloaded filename: ${suggested}`);
  fs.mkdirSync(input.outputDir, { recursive: true });
  const outputPath = path.join(input.outputDir, suggested);
  await download.saveAs(outputPath);
  if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) throw new Error("Downloaded CSV is missing or empty");
  return { status: "downloaded", kind: input.kind, csvPath: outputPath, bytes: fs.statSync(outputPath).size };
}

export async function uploadMercariTimesaleCsv(page, rawInput) {
  const input = validateUploadInput(rawInput);
  verifyShopContext(page, input.shopId);
  const uploadUrl = `${BASE}/${input.shopId}/dualprice/upload`;
  await page.goto(uploadUrl);
  await page.getByRole("heading", { name: "タイムセールを一括設定する", exact: true }).waitFor();

  const basename = path.basename(input.csvPath);
  const existing = page.getByText(basename, { exact: true });
  if ((await existing.count()) > 0) throw new Error(`A history entry already exists for ${basename}; inspect it before retrying`);
  const fileInput = page.locator('input[type="file"]');
  if ((await fileInput.count()) !== 1) throw new Error("Could not uniquely locate the time-sale CSV file input");
  await fileInput.setInputFiles(input.csvPath);

  const filename = page.getByText(basename, { exact: true }).first();
  await filename.waitFor({ state: "visible", timeout: 120000 });
  const row = filename.locator('xpath=ancestor::*[self::tr or @role="row"][1]');
  if ((await row.count()) !== 1) throw new Error("Uploaded filename appeared but its history row could not be identified");
  const rowText = (await row.innerText()).trim();
  const state = /設定完了/.test(rowText) ? "completed" : /エラー/.test(rowText) ? "error" : /設定を再開する/.test(rowText) ? "resumable" : "uploaded";
  const errorDownloadAvailable = (await row.getByRole("button", { name: "ダウンロード", exact: true }).count()) > 0;
  return { status: "uploaded", filename: basename, historyState: state, errorDownloadAvailable, stoppedBeforeApply: true };
}

