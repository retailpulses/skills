/**
 * XML serialization and deserialization for Rakuten RMS CouponAPI.
 *
 * XML format verified against Go SDK (github.com/bububa/rakuten-go):
 *   Request:  <request><couponIssueRequest><coupon>...fields...</coupon></couponIssueRequest></request>
 *   Response: <result><status/><couponIssueResult><couponCode/></...></result>
 *
 * Go SDK reference structs:
 *   IssueRequest{ XMLName xml.Name `xml:"couponIssueRequest"`; Coupon *CouponToIssue `xml:"coupon"` }
 *   XMLRequest[T]{ XMLName xml.Name `xml:"request"`; Content T `xml:",any"` }
 *
 * Field XML names match Go struct tags exactly (camelCase, no prefix).
 */

import type { CouponToIssue, CouponDeleteRequest } from "../dto/coupon.js";

// ─── XML escaping ───────────────────────────────────────────────

export function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export const XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>';

// ─── Response parser (fast-xml-parser) ──────────────────────────

const ARRAY_ELEMENTS = [
  "coupon", "thanksCoupon", "item", "error",
  "otherCondition", "thanksOtherCondition", "thanksAutoGetCondition",
  "rankCond", "prefectureCond",
];

import { XMLParser } from "fast-xml-parser";

const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: "@_",
  isArray: (name) => ARRAY_ELEMENTS.includes(name),
  textNodeName: "#text",
  ignoreDeclaration: false,
  removeNSPrefix: true,
});

export function parseXmlResponse<T>(xml: string): T {
  return parser.parse(xml) as unknown as T;
}

// ─── Shared coupon field serialization ──────────────────────────

/**
 * Build XML elements for CouponToIssue fields.
 * Element names match Go SDK xml tags EXACTLY.
 */
function couponFields(coupon: CouponToIssue, indent: string): string[] {
  const lines: string[] = [];
  const I = indent;

  // Required fields (in declaration order from Go SDK)
  lines.push(`${I}<couponName>${escapeXml(coupon.couponName)}</couponName>`);
  lines.push(`${I}<couponCaption>${escapeXml(coupon.couponCaption)}</couponCaption>`);
  lines.push(`${I}<couponStartDate>${escapeXml(coupon.couponStartDate)}</couponStartDate>`);
  lines.push(`${I}<couponEndDate>${escapeXml(coupon.couponEndDate)}</couponEndDate>`);
  lines.push(`${I}<issueCount>${coupon.issueCount}</issueCount>`);
  lines.push(`${I}<itemType>${coupon.itemType}</itemType>`);
  lines.push(`${I}<discountType>${coupon.discountType}</discountType>`);
  lines.push(`${I}<discountFactor>${coupon.discountFactor}</discountFactor>`);
  lines.push(`${I}<combineFlag>${coupon.combineFlag}</combineFlag>`);

  // Optional: couponImage
  if (coupon.couponImage) {
    lines.push(`${I}<couponImage>${escapeXml(coupon.couponImage)}</couponImage>`);
  }

  // Optional: memberAvailMaxCount
  if (coupon.memberAvailMaxCount !== undefined) {
    lines.push(`${I}<memberAvailMaxCount>${coupon.memberAvailMaxCount}</memberAvailMaxCount>`);
  }

  // Optional: displayFlag
  if (coupon.displayFlag !== undefined) {
    lines.push(`${I}<displayFlag>${coupon.displayFlag}</displayFlag>`);
  }

  // Rank conditions: multiRankCond, genderCond, ageRangeCond, birthmonthCond, multiPrefectureCond
  if (coupon.rankCondition) {
    const rc = coupon.rankCondition;
    if (rc.gender !== undefined) {
      lines.push(`${I}<genderCond>${rc.gender}</genderCond>`);
    }
    if (rc.age !== undefined) {
      lines.push(`${I}<ageRangeCond>`);
      lines.push(`${I}  <lowerBound>${rc.age}</lowerBound>`);
      lines.push(`${I}</ageRangeCond>`);
    }
    if (rc.prefecture) {
      lines.push(`${I}<multiPrefectureCond>`);
      lines.push(`${I}  <prefectureCond>${escapeXml(rc.prefecture)}</prefectureCond>`);
      lines.push(`${I}</multiPrefectureCond>`);
    }
    if (rc.rankCode !== undefined) {
      lines.push(`${I}<multiRankCond>`);
      lines.push(`${I}  <rankCond>${rc.rankCode}</rankCond>`);
      lines.push(`${I}</multiRankCond>`);
    }
  }

  // Items: <items><item><itemUrl>...</itemUrl></item></items>
  if (coupon.items && coupon.items.length > 0) {
    lines.push(`${I}<items>`);
    for (const item of coupon.items) {
      lines.push(`${I}  <item>`);
      lines.push(`${I}    <itemUrl>${escapeXml(item.itemUrl)}</itemUrl>`);
      lines.push(`${I}  </item>`);
    }
    lines.push(`${I}</items>`);
  }

  // OtherConditions: <otherConditions><otherCondition>...</...></otherConditions>
  if (coupon.otherConditions && coupon.otherConditions.length > 0) {
    lines.push(`${I}<otherConditions>`);
    for (const cond of coupon.otherConditions) {
      lines.push(`${I}  <otherCondition>`);
      lines.push(`${I}    <conditionTypeCode>${escapeXml(cond.conditionTypeCode)}</conditionTypeCode>`);
      lines.push(`${I}    <startValue>${escapeXml(cond.startValue)}</startValue>`);
      lines.push(`${I}  </otherCondition>`);
    }
    lines.push(`${I}</otherConditions>`);
  }

  return lines;
}

// ─── Coupon issue XML ───────────────────────────────────────────

/**
 * Build XML for issuing a coupon.
 *
 * Matches Go SDK: XMLRequest[IssueRequest{ Coupon: *CouponToIssue }]
 *   <request>
 *     <couponIssueRequest>
 *       <coupon>
 *         <couponName>...</couponName>
 *         <issueCount>5000</issueCount>
 *         ...
 *       </coupon>
 *     </couponIssueRequest>
 *   </request>
 */
export function buildCouponIssueXml(coupon: CouponToIssue): string {
  return [
    XML_HEADER,
    "<request>",
    "  <couponIssueRequest>",
    "    <coupon>",
    ...couponFields(coupon, "      "),
    "    </coupon>",
    "  </couponIssueRequest>",
    "</request>",
  ].join("\n");
}

// ─── Coupon update XML ──────────────────────────────────────────

/**
 * Build XML for updating a coupon.
 * Same wrapper as issue but with <couponCode> inside <coupon>.
 */
export function buildCouponUpdateXml(coupon: CouponToIssue & { couponCode: string }): string {
  return [
    XML_HEADER,
    "<request>",
    "  <couponUpdateRequest>",
    "    <coupon>",
    `      <couponCode>${escapeXml(coupon.couponCode)}</couponCode>`,
    ...couponFields(coupon, "      "),
    "    </coupon>",
    "  </couponUpdateRequest>",
    "</request>",
  ].join("\n");
}

// ─── Coupon delete XML ──────────────────────────────────────────

/**
 * Build XML for deleting a coupon.
 */
export function buildCouponDeleteXml(req: CouponDeleteRequest): string {
  return [
    XML_HEADER,
    "<request>",
    "  <couponDeleteRequest>",
    "    <coupon>",
    `      <couponCode>${escapeXml(req.couponCode)}</couponCode>`,
    "    </coupon>",
    "  </couponDeleteRequest>",
    "</request>",
  ].join("\n");
}
