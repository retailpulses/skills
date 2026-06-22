/**
 * Clone the structure of a working coupon to find the required XML format.
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

  // Try EXACTLY the structure from the working coupon, just rename + change date
  // Include ALL the same optional elements: couponImage, multiRankCond, otherConditions
  const xmls: Array<{ name: string; xml: string }> = [
    {
      name: "A: Exact clone structure (all fields, image, rank, conditions)",
      xml: `<?xml version="1.0" encoding="UTF-8"?>
<request>
  <couponIssueRequest>
    <coupon>
      <couponName>買い物マラソン テスト</couponName>
      <couponCaption>テスト</couponCaption>
      <couponStartDate>2026-06-20T20:00:00+09:00</couponStartDate>
      <couponEndDate>2026-06-26T01:59:00+09:00</couponEndDate>
      <couponImage>https://image.rakuten.co.jp/homebliss/logo/logo1.jpg</couponImage>
      <issueCount>100</issueCount>
      <itemType>4</itemType>
      <discountType>2</discountType>
      <discountFactor>5</discountFactor>
      <memberAvailMaxCount>0</memberAvailMaxCount>
      <multiRankCond>
        <rankCond>0</rankCond>
      </multiRankCond>
      <combineFlag>0</combineFlag>
      <displayFlag>1</displayFlag>
      <otherConditions>
        <otherCondition>
          <conditionTypeCode>RS001</conditionTypeCode>
          <startValue>0</startValue>
        </otherCondition>
        <otherCondition>
          <conditionTypeCode>RS001</conditionTypeCode>
          <startValue>1</startValue>
        </otherCondition>
        <otherCondition>
          <conditionTypeCode>RS002</conditionTypeCode>
          <startValue>0</startValue>
        </otherCondition>
      </otherConditions>
    </coupon>
  </couponIssueRequest>
</request>`,
    },
    {
      name: "B: Minimal — only required fields, no optionals",
      xml: `<?xml version="1.0" encoding="UTF-8"?>
<request>
  <couponIssueRequest>
    <coupon>
      <couponName>テスト最小</couponName>
      <couponCaption>最小テスト</couponCaption>
      <couponStartDate>2026-06-20T20:00:00+09:00</couponStartDate>
      <couponEndDate>2026-06-26T01:59:00+09:00</couponEndDate>
      <issueCount>100</issueCount>
      <itemType>4</itemType>
      <discountType>2</discountType>
      <discountFactor>5</discountFactor>
      <combineFlag>0</combineFlag>
    </coupon>
  </couponIssueRequest>
</request>`,
    },
    {
      name: "C: Required + displayFlag + memberAvailMaxCount=0",
      xml: `<?xml version="1.0" encoding="UTF-8"?>
<request>
  <couponIssueRequest>
    <coupon>
      <couponName>テスト表示設定</couponName>
      <couponCaption>表示テスト</couponCaption>
      <couponStartDate>2026-06-20T20:00:00+09:00</couponStartDate>
      <couponEndDate>2026-06-26T01:59:00+09:00</couponEndDate>
      <issueCount>100</issueCount>
      <itemType>4</itemType>
      <discountType>2</discountType>
      <discountFactor>5</discountFactor>
      <memberAvailMaxCount>0</memberAvailMaxCount>
      <combineFlag>0</combineFlag>
      <displayFlag>1</displayFlag>
    </coupon>
  </couponIssueRequest>
</request>`,
    },
  ];

  for (const v of xmls) {
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
    const code = body.match(/<couponCode>(.*?)<\/couponCode>/)?.[1];
    console.log(`HTTP ${resp.status} | status=${status} | ${msg}`);
    if (code) {
      console.log(`✅ ISSUED! couponCode=${code}`);
    }
    if (status !== "OK") {
      // Print error details
      const errorCodes = [...body.matchAll(/<code>(.*?)<\/code>/g)].map(m => m[1]);
      const errorMsgs = [...body.matchAll(/<error>[\s\S]*?<message>(.*?)<\/message>[\s\S]*?<\/error>/g)].map(m => m[1]);
      if (errorCodes.length > 0) {
        console.log("Errors:", errorCodes.map((c, i) => `[${c}] ${errorMsgs[i] || ""}`).join("; "));
      }
    }
  }
}

main().catch(console.error);
