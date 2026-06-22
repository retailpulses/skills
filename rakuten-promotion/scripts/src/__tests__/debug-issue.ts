/**
 * Debug: send a minimal coupon issue request and print full response.
 */
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

async function main() {
  const env = parseEnvFile(resolve(process.env.HOME!, "Documents/Rakuten/.env"));
  const ss = env["RAKUTEN_SERVICE_SECRET"]!;
  const lk = env["RAKUTEN_LICENSE_KEY"]!;

  const authRaw = `${ss}:${lk}`;
  const bytes = new TextEncoder().encode(authRaw);
  const binary = String.fromCharCode(...bytes);
  const encoded = btoa(binary);

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<request>
  <couponIssueRequest>
    <coupon>
      <couponName>テスト</couponName>
      <couponCaption>テスト</couponCaption>
      <couponStartDate>2026-06-20T20:00:00+09:00</couponStartDate>
      <couponEndDate>2026-06-26T01:59:00+09:00</couponEndDate>
      <issueCount>100</issueCount>
      <itemType>4</itemType>
      <discountType>2</discountType>
      <discountFactor>5</discountFactor>
      <combineFlag>0</combineFlag>
    </coupon>
  </couponIssueRequest>
</request>`;

  console.log("=== SENDING ===");
  console.log(xml);
  console.log("");

  const resp = await fetch("https://api.rms.rakuten.co.jp/es/1.0/coupon/issue", {
    method: "POST",
    headers: {
      Authorization: `ESA ${encoded}`,
      "Content-Type": "application/xml; charset=utf-8",
      Accept: "application/xml",
    },
    body: xml,
  });

  const body = await resp.text();
  console.log(`=== RESPONSE HTTP ${resp.status} ===`);
  console.log(body);
}

main().catch(console.error);
