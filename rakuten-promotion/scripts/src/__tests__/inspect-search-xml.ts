/**
 * Fetch raw XML from coupon search and print ALL element names.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function parseEnv(path: string) {
  const c = readFileSync(path, "utf-8");
  const env: Record<string, string> = {};
  for (const line of c.split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const i = t.indexOf("=");
    if (i === -1) continue;
    let v = t.slice(i + 1).trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    env[t.slice(0, i).trim()] = v;
  }
  return env;
}

async function main() {
  const env = parseEnv(resolve(process.env.HOME!, "Documents/Rakuten/.env"));
  const ss = env["RAKUTEN_SERVICE_SECRET"]!;
  const lk = env["RAKUTEN_LICENSE_KEY"]!;
  const auth = `ESA ${btoa(String.fromCharCode(...new TextEncoder().encode(`${ss}:${lk}`)))}`;

  // Search for 1 coupon to get raw XML
  const url = "https://api.rms.rakuten.co.jp/es/1.0/coupon/search?hits=1";
  const resp = await fetch(url, {
    headers: { Authorization: auth, Accept: "application/xml" },
  });

  const xml = await resp.text();
  console.log("=== RAW SEARCH RESPONSE XML ===");
  console.log(xml);

  // Extract all element names
  const elementPattern = /<\/?([a-zA-Z][a-zA-Z0-9]*)/g;
  const elements = new Set<string>();
  let match;
  while ((match = elementPattern.exec(xml)) !== null) {
    elements.add(match[1]);
  }
  console.log("\n=== ALL ELEMENT NAMES ===");
  for (const el of [...elements].sort()) {
    console.log(`  ${el}`);
  }
}

main().catch(console.error);
