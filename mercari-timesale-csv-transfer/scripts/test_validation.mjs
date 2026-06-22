import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { validateDownloadInput, validateUploadInput } from "./mercari_timesale_csv_playwright.mjs";

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "timesale-skill-"));
const csvPath = path.join(tempDir, "timesale.csv");
fs.writeFileSync(csvPath, "header\nvalue\n");

assert.equal(validateDownloadInput({ shopId: "SHOP123", outputDir: tempDir }).kind, "registration");
assert.equal(validateDownloadInput({ shopId: "SHOP123", outputDir: tempDir, kind: "existing" }).kind, "existing");
assert.equal(validateUploadInput({ shopId: "SHOP123", csvPath }).csvPath, csvPath);
assert.throws(() => validateDownloadInput({ shopId: "", outputDir: tempDir }), /shopId/);
assert.throws(() => validateDownloadInput({ shopId: "SHOP123", outputDir: "relative" }), /absolute/);
assert.throws(() => validateUploadInput({ shopId: "SHOP123", csvPath: path.join(tempDir, "missing.csv") }), /does not exist/);

console.log("Mercari time-sale CSV transfer validation tests passed.");
