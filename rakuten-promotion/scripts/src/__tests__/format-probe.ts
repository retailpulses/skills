/**
 * Probe: try different XML formats to find what Rakuten accepts.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function parseEnv(path: string) {
  const content = readFileSync(path, "utf-8");
  const env: Record<string, string> = {};
  for (const line of content.split("\n")) {
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

const FIELDS = [
  "<couponName>テスト</couponName>",
  "<couponCaption>テスト</couponCaption>",
  "<couponStartDate>2026-06-20T20:00:00+09:00</couponStartDate>",
  "<couponEndDate>2026-06-26T01:59:00+09:00</couponEndDate>",
  "<issueCount>100</issueCount>",
  "<itemType>4</itemType>",
  "<discountType>2</discountType>",
  "<discountFactor>5</discountFactor>",
  "<combineFlag>0</combineFlag>",
].join("\n");

const HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n';

interface Variant {
  name: string;
  xml: string;
}

const variants: Variant[] = [
  {
    name: "V1: <request><couponIssueRequest><coupon> (current)",
    xml: `${HEADER}<request>\n  <couponIssueRequest>\n    <coupon>\n${FIELDS}\n    </coupon>\n  </couponIssueRequest>\n</request>`,
  },
  {
    name: "V2: <request> only (no couponIssueRequest wrapper)",
    xml: `${HEADER}<request>\n  <coupon>\n${FIELDS}\n  </coupon>\n</request>`,
  },
  {
    name: "V3: <couponIssueRequest> root (no <request>)",
    xml: `${HEADER}<couponIssueRequest>\n  <coupon>\n${FIELDS}\n  </coupon>\n</couponIssueRequest>`,
  },
  {
    name: "V4: fields directly under <request> (flat)",
    xml: `${HEADER}<request>\n${FIELDS}\n</request>`,
  },
  {
    name: "V5: <request><couponIssueRequest> flat (no <coupon>)",
    xml: `${HEADER}<request>\n  <couponIssueRequest>\n${FIELDS}\n  </couponIssueRequest>\n</request>`,
  },
];

async function main() {
  const env = parseEnv(resolve(process.env.HOME!, "Documents/Rakuten/.env"));
  const ss = env["RAKUTEN_SERVICE_SECRET"]!;
  const lk = env["RAKUTEN_LICENSE_KEY"]!;
  const auth = `ESA ${btoa(String.fromCharCode(...new TextEncoder().encode(`${ss}:${lk}`)))}`;

  for (const v of variants) {
    console.log(`\n=== ${v.name} ===`);
    const resp = await fetch("https://api.rms.rakuten.co.jp/es/1.0/coupon/issue", {
      method: "POST",
      headers: {
        Authorization: auth,
        "Content-Type": "application/xml; charset=utf-8",
        Accept: "application/xml",
      },
      body: v.xml,
    });
    const body = await resp.text();
    const status = body.match(/<systemStatus>(OK|NG)<\/systemStatus>/)?.[1] ?? "?";
    const msg = body.match(/<message>(.*?)<\/message>/)?.[1] ?? "?";
    console.log(`HTTP ${resp.status} | status=${status} | ${msg}`);

    if (status === "OK") {
      console.log("✅ WINNER! Full response:");
      console.log(body);
      break;
    }
  }
}

main().catch(console.error);
