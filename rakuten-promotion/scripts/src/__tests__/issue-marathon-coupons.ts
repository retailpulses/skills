/**
 * ISSUE 4 coupons for 買い物マラソン June 2026.
 * PRODUCTION — issues real coupons to Rakuten RMS.
 */
import { createPromotionClient } from "../index.js";
import type { CouponToIssue } from "../dto/coupon.js";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function parseEnvFile(path: string): Record<string, string> {
  const content = readFileSync(path, "utf-8");
  const env: Record<string, string> = {};
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    let value = trimmed.slice(eqIdx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

const coupons: Array<{ label: string; payload: CouponToIssue }> = [
  {
    label: "#1 5% Campaign-wide",
    payload: {
      couponName: "買い物マラソン 店内全品5%OFF",
      couponCaption: "店内全品5%OFFクーポン",
      couponStartDate: "2026-06-20T20:00:00+09:00",
      couponEndDate: "2026-06-26T01:59:00+09:00",
      issueCount: 5000,
      itemType: 4, discountType: 2, discountFactor: 5,
      combineFlag: 0, displayFlag: 1, memberAvailMaxCount: 1,
    },
  },
  {
    label: "#2 10% Opening Flash",
    payload: {
      couponName: "買い物マラソン 開始2時間限定10%OFF",
      couponCaption: "開始2時間限定 店内全品10%OFF",
      couponStartDate: "2026-06-20T20:00:00+09:00",
      couponEndDate: "2026-06-20T22:00:00+09:00",
      issueCount: 2000,
      itemType: 4, discountType: 2, discountFactor: 10,
      combineFlag: 0, displayFlag: 1, memberAvailMaxCount: 1,
    },
  },
  {
    label: "#3 7% Weekend Push",
    payload: {
      couponName: "買い物マラソン 週末限定7%OFF",
      couponCaption: "土日限定 店内全品7%OFF",
      couponStartDate: "2026-06-20T20:00:00+09:00",
      couponEndDate: "2026-06-22T01:59:00+09:00",
      issueCount: 3000,
      itemType: 4, discountType: 2, discountFactor: 7,
      combineFlag: 0, displayFlag: 1, memberAvailMaxCount: 1,
    },
  },
  {
    label: "#4 8% Last-Day Close",
    payload: {
      couponName: "買い物マラソン 最終日8%OFF",
      couponCaption: "買い物マラソン最終日 店内8%OFF",
      couponStartDate: "2026-06-25T00:00:00+09:00",
      couponEndDate: "2026-06-26T01:59:00+09:00",
      issueCount: 2000,
      itemType: 4, discountType: 2, discountFactor: 8,
      combineFlag: 0, displayFlag: 1, memberAvailMaxCount: 1,
    },
  },
];

async function main() {
  const envPath = resolve(process.env.HOME!, "Documents/Rakuten/.env");
  const env = parseEnvFile(envPath);

  const client = createPromotionClient({
    serviceSecret: env["RAKUTEN_SERVICE_SECRET"]!,
    licenseKey: env["RAKUTEN_LICENSE_KEY"]!,
    rateLimitDelayMs: 2000, // conservative: 1 req / 2 sec
  });

  console.log("═══════════════════════════════════════════════");
  console.log(" ISSUING 買い物マラソン Coupons — PRODUCTION");
  console.log("═══════════════════════════════════════════════\n");

  const issued: Array<{ label: string; code: string; url: string }> = [];
  const errors: Array<{ label: string; error: string }> = [];

  for (const { label, payload } of coupons) {
    console.log(`▶ ${label}: ${payload.couponName}`);
    try {
      const result = await client.coupon.issue(payload);
      console.log(`  ✅ Issued: ${result.couponCode}`);
      console.log(`  🔗 URL:    ${result.pcGetUrl}`);
      issued.push({ label, code: result.couponCode, url: result.pcGetUrl });
    } catch (err: any) {
      console.error(`  ❌ FAILED: ${err.message}`);
      if (err.errors) {
        for (const e of err.errors) {
          console.error(`     [${e.code}] ${e.message}`);
        }
      }
      errors.push({ label, error: err.message });
    }
    console.log();
  }

  console.log("═══════════════════════════════════════════════");
  console.log(` Issued: ${issued.length}/${coupons.length}`);
  console.log(` Failed: ${errors.length}/${coupons.length}`);
  console.log("═══════════════════════════════════════════════");

  if (issued.length > 0) {
    console.log("\nRollback commands:");
    for (const { label, code } of issued) {
      console.log(`  client.coupon.delete({ couponCode: "${code}" })  // ${label}`);
    }
  }
}

main().catch(console.error);
