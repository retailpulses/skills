/**
 * Live smoke test: read past coupons from Rakuten RMS using credentials from .env.
 * Read-only — no mutations.
 *
 * Usage: npx tsx src/__tests__/live-search.ts
 */
import { createPromotionClient } from "../index.js";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Parse .env file without dotenv dependency
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
    // Strip surrounding quotes
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

async function main() {
  // Load credentials
  const envPath = resolve(process.env.HOME!, "Documents/Rakuten/.env");
  console.log(`Loading credentials from: ${envPath}`);
  const env = parseEnvFile(envPath);

  const serviceSecret = env["RAKUTEN_SERVICE_SECRET"];
  const licenseKey = env["RAKUTEN_LICENSE_KEY"];

  if (!serviceSecret || !licenseKey) {
    console.error("Missing RAKUTEN_SERVICE_SECRET or RAKUTEN_LICENSE_KEY in .env");
    process.exit(1);
  }

  console.log(`Service secret: ${serviceSecret.slice(0, 4)}****${serviceSecret.slice(-4)}`);
  console.log(`License key:    ${licenseKey.slice(0, 4)}****${licenseKey.slice(-4)}`);

  // Create client
  const client = createPromotionClient({
    serviceSecret,
    licenseKey,
    rateLimitDelayMs: 1500, // conservative
  });

  // Test 1: Search for recent coupons (small page)
  console.log("\n--- Test 1: Search coupons (hits=5) ---");
  try {
    const result = await client.coupon.search({ hits: 5 });
    console.log(`Total coupons: ${result.allCount}`);
    console.log(`Page items:    ${result.coupons.length}`);
    for (const c of result.coupons) {
      console.log(`  [${c.couponCode}] ${c.couponName} — ${c.couponCaption}`);
      console.log(`    Period: ${c.couponStartDate} → ${c.couponEndDate}`);
      console.log(`    Type: ${c.discountType}, Factor: ${c.discountFactor}, Issued: ${c.issueCount}`);
    }
  } catch (err: any) {
    console.error("Search failed:", err.message);
    if (err.errors) {
      for (const e of err.errors) {
        console.error(`  [${e.code}] ${e.message}`);
      }
    }
  }

  // Test 2: Search by name (partial match)
  console.log("\n--- Test 2: Search by name 'サマー' ---");
  try {
    const result = await client.coupon.search({ couponName: "サマー", hits: 3 });
    console.log(`Found: ${result.allCount} matching`);
    for (const c of result.coupons) {
      console.log(`  [${c.couponCode}] ${c.couponName}`);
    }
  } catch (err: any) {
    console.error("Search by name failed:", err.message);
  }

  // Test 3: Check license expiry via LicenseManagementAPI
  console.log("\n--- Test 3: License key expiry ---");
  try {
    const url = "https://api.rms.rakuten.co.jp/es/1.0/license-management/license-key/expiry-date";
    const auth = `ESA ${btoa(`${serviceSecret}:${licenseKey}`)}`;
    const res = await fetch(`${url}?licenseKey=${encodeURIComponent(licenseKey)}`, {
      headers: { Authorization: auth, Accept: "application/json" },
    });
    const data = await res.json();
    console.log(`HTTP ${res.status}:`, JSON.stringify(data, null, 2));
  } catch (err: any) {
    console.error("License check failed:", err.message);
  }

  console.log("\n✅ Live smoke test complete.");
}

main().catch(console.error);
