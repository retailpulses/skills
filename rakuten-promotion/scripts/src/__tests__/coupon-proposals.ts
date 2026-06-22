/**
 * 買い物マラソン June 2026 — Coupon Proposals for homebliss
 *
 * Campaign: June 20 (Sat) 20:00 → June 26 (Fri) 01:59 JST
 *
 * Strategy based on past coupon analysis:
 *   - Shop uses time-limited flash coupons (4-6hr windows, 10% OFF)
 *   - All past coupons were discountType=2 (percentage), itemType=4 (entire order)
 *   - We add a campaign-long base coupon (5%) + opening flash (10%)
 *
 * Run: npx tsx src/__tests__/coupon-proposals.ts
 */

import { createPromotionClient, validateCouponToIssue } from "../index.js";
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

// ─── Campaign window ────────────────────────────────────────────

const MARATHON_START = "2026-06-20T20:00:00+09:00";
const MARATHON_END   = "2026-06-26T01:59:00+09:00";
const MARATHON_LABEL  = "買い物マラソン";

// ─── Proposal definitions ───────────────────────────────────────

interface Proposal {
  name: string;
  description: string;
  coupon: CouponToIssue;
}

const proposals: Proposal[] = [
  {
    name: "Campaign-wide 5% OFF",
    description:
      "Runs the entire marathon. Lower barrier (5%) encourages casual shoppers. " +
      "ItemType=4 (entire order) — simplest, broadest reach. CombineFlag=0 prevents stacking abuse.",
    coupon: {
      couponName: `${MARATHON_LABEL} 店内全品5%OFF`,
      couponCaption: "店内全品5%OFFクーポン",
      couponStartDate: MARATHON_START,
      couponEndDate: MARATHON_END,
      issueCount: 5000,
      itemType: 4,         // entire order
      discountType: 2,     // percentage
      discountFactor: 5,   // 5%
      combineFlag: 0,      // no combine
      displayFlag: 1,      // visible on shop page
      memberAvailMaxCount: 1,
    },
  },
  {
    name: "Opening 2hr Flash 10% OFF",
    description:
      "Matches 開始2時間限定 pattern from past campaigns. High urgency drives initial spike. " +
      "10% OFF for the first 2 hours only (20:00-22:00 on June 20).",
    coupon: {
      couponName: `${MARATHON_LABEL} 開始2時間限定10%OFF`,
      couponCaption: "開始2時間限定 店内全品10%OFF",
      couponStartDate: "2026-06-20T20:00:00+09:00",
      couponEndDate: "2026-06-20T22:00:00+09:00",
      issueCount: 2000,
      itemType: 4,
      discountType: 2,
      discountFactor: 10,  // 10%
      combineFlag: 0,
      displayFlag: 1,
      memberAvailMaxCount: 1,
    },
  },
  {
    name: "Weekend Push 7% OFF (Sat-Sun)",
    description:
      "Higher discount for weekend shoppers. Overlaps with the opening flash " +
      "but runs through Sunday night. Mid-tier between 5% base and 10% flash.",
    coupon: {
      couponName: `${MARATHON_LABEL} 週末限定7%OFF`,
      couponCaption: "土日限定 店内全品7%OFF",
      couponStartDate: "2026-06-20T20:00:00+09:00",
      couponEndDate: "2026-06-22T01:59:00+09:00", // through early Mon
      issueCount: 3000,
      itemType: 4,
      discountType: 2,
      discountFactor: 7,   // 7%
      combineFlag: 0,
      displayFlag: 1,
      memberAvailMaxCount: 1,
    },
  },
  {
    name: "Last-Day Close 8% OFF",
    description:
      "Urgency close on the final day. Slightly higher than base but below 10%. " +
      "Push fence-sitters to convert before the marathon ends.",
    coupon: {
      couponName: `${MARATHON_LABEL} 最終日8%OFF`,
      couponCaption: "買い物マラソン最終日 店内8%OFF",
      couponStartDate: "2026-06-25T00:00:00+09:00",
      couponEndDate: MARATHON_END,
      issueCount: 2000,
      itemType: 4,
      discountType: 2,
      discountFactor: 8,   // 8%
      combineFlag: 0,
      displayFlag: 1,
      memberAvailMaxCount: 1,
    },
  },
];

// ─── Main ───────────────────────────────────────────────────────

async function main() {
  const envPath = resolve(process.env.HOME!, "Documents/Rakuten/.env");
  const env = parseEnvFile(envPath);

  const client = createPromotionClient({
    serviceSecret: env["RAKUTEN_SERVICE_SECRET"]!,
    licenseKey: env["RAKUTEN_LICENSE_KEY"]!,
    dryRun: true, // SAFE: validate only, no actual issue
  });

  console.log("═══════════════════════════════════════════════════════");
  console.log(" 買い物マラソン June 2026 — Coupon Proposals");
  console.log(" Campaign: June 20 (Sat) 20:00 → June 26 (Fri) 01:59");
  console.log(" Shop: homebliss");
  console.log("═══════════════════════════════════════════════════════\n");

  let allValid = true;

  for (const proposal of proposals) {
    console.log(`▸ ${proposal.name}`);
    console.log(`  ${proposal.description}\n`);

    // Validate
    const validationErrors = validateCouponToIssue(proposal.coupon);
    if (validationErrors.length > 0) {
      console.log("  ❌ VALIDATION ERRORS:");
      for (const e of validationErrors) {
        console.log(`     - ${e.message}`);
      }
      allValid = false;
    } else {
      console.log("  ✅ Validation passed");
    }

    // Dry-run issue (logs XML, returns fake result)
    try {
      const result = await client.coupon.issue(proposal.coupon);
      console.log(`  🏷  Would issue: ${result.couponCode}`);
    } catch (err: any) {
      console.log(`  ❌ Would fail: ${err.message}`);
      allValid = false;
    }

    // Summary table row
    const c = proposal.coupon;
    console.log(`  📋 ${c.couponName}`);
    console.log(`     Period:  ${c.couponStartDate} → ${c.couponEndDate}`);
    console.log(`     Discount: ${c.discountFactor}% | Issued: ${c.issueCount.toLocaleString()} | Type: ${c.itemType}`);
    console.log();
  }

  console.log("═══════════════════════════════════════════════════════");
  console.log(allValid ? "✅ All proposals validate." : "❌ Some proposals have errors.");
  console.log("   Run without dryRun to issue (requires confirmation).");
  console.log("═══════════════════════════════════════════════════════");
}

main().catch(console.error);
