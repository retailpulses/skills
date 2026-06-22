/**
 * Tests for XML serialization and deserialization.
 */
import { describe, it, expect } from "vitest";
import {
  escapeXml,
  parseXmlResponse,
  buildCouponIssueXml,
  buildCouponUpdateXml,
  buildCouponDeleteXml,
  XML_HEADER,
} from "../parser/xml.js";
import type { CouponToIssue } from "../dto/coupon.js";

describe("escapeXml", () => {
  it("escapes ampersand", () => {
    expect(escapeXml("A & B")).toBe("A &amp; B");
  });

  it("escapes less than", () => {
    expect(escapeXml("x < 5")).toBe("x &lt; 5");
  });

  it("escapes greater than", () => {
    expect(escapeXml("x > 5")).toBe("x &gt; 5");
  });

  it("escapes double quote", () => {
    expect(escapeXml('say "hello"')).toBe("say &quot;hello&quot;");
  });

  it("handles strings without special chars", () => {
    expect(escapeXml("普通のテキスト")).toBe("普通のテキスト");
  });
});

describe("parseXmlResponse", () => {
  it("parses simple XML", () => {
    const xml = "<result><status><systemStatus>OK</systemStatus></status></result>";
    const parsed = parseXmlResponse<{ result: { status: { systemStatus: string } } }>(xml);
    expect(parsed.result.status.systemStatus).toBe("OK");
  });

  it("parses arrays from single element via isArray config", () => {
    const xml = `<result><coupons><coupon><couponCode>C1</couponCode></coupon></coupons></result>`;
    const parsed = parseXmlResponse<{
      result: { coupons: { coupon: Array<{ couponCode: string }> } };
    }>(xml);
    expect(Array.isArray(parsed.result.coupons.coupon)).toBe(true);
    expect(parsed.result.coupons.coupon[0].couponCode).toBe("C1");
  });
});

const minimalCoupon: CouponToIssue = {
  couponName: "テストクーポン",
  couponCaption: "テスト",
  couponStartDate: "2026-07-01T00:00:00+09:00",
  couponEndDate: "2026-07-31T23:59:59+09:00",
  issueCount: 100,
  itemType: 4,
  discountType: 2,
  discountFactor: 10,
  combineFlag: 0,
};

describe("buildCouponIssueXml", () => {
  it("produces valid XML with header", () => {
    const xml = buildCouponIssueXml(minimalCoupon);
    expect(xml).toContain(XML_HEADER);
    expect(xml).toContain("<request>");
    expect(xml).toContain("<couponIssueRequest>");
    expect(xml).toContain("<coupon>");
    expect(xml).toContain("<couponName>テストクーポン</couponName>");
    expect(xml).toContain("<issueCount>100</issueCount>");
    expect(xml).toContain("<discountType>2</discountType>");
    expect(xml).toContain("<discountFactor>10</discountFactor>");
    expect(xml).toContain("</coupon>");
    expect(xml).toContain("</couponIssueRequest>");
    expect(xml).toContain("</request>");
  });

  it("escapes special chars in name", () => {
    const c = { ...minimalCoupon, couponName: "A & B < C" };
    const xml = buildCouponIssueXml(c);
    expect(xml).toContain("A &amp; B &lt; C");
  });

  it("includes optional fields when present", () => {
    const c: CouponToIssue = {
      ...minimalCoupon,
      couponImage: "https://example.com/img.jpg",
      memberAvailMaxCount: 3,
      displayFlag: 1,
    };
    const xml = buildCouponIssueXml(c);
    expect(xml).toContain("<couponImage>https://example.com/img.jpg</couponImage>");
    expect(xml).toContain("<memberAvailMaxCount>3</memberAvailMaxCount>");
    expect(xml).toContain("<displayFlag>1</displayFlag>");
  });

  it("omits optional fields when absent", () => {
    const xml = buildCouponIssueXml(minimalCoupon);
    expect(xml).not.toContain("<couponImage>");
    expect(xml).not.toContain("<memberAvailMaxCount>");
  });

  it("includes items when present", () => {
    const c: CouponToIssue = {
      ...minimalCoupon,
      itemType: 1,
      items: [
        { itemUrl: "https://item.rakuten.co.jp/shop/a/" },
        { itemUrl: "https://item.rakuten.co.jp/shop/b/" },
      ],
    };
    const xml = buildCouponIssueXml(c);
    expect(xml).toContain("<items>");
    expect(xml).toContain("<itemUrl>https://item.rakuten.co.jp/shop/a/</itemUrl>");
    expect(xml).toContain("<itemUrl>https://item.rakuten.co.jp/shop/b/</itemUrl>");
    expect(xml).toContain("</items>");
  });

  it("includes rank conditions when present", () => {
    const c: CouponToIssue = {
      ...minimalCoupon,
      rankCondition: { gender: 1, rankCode: 2 },
    };
    const xml = buildCouponIssueXml(c);
    expect(xml).toContain("<genderCond>1</genderCond>");
    expect(xml).toContain("<rankCond>2</rankCond>");
  });

  it("includes other conditions when present", () => {
    const c: CouponToIssue = {
      ...minimalCoupon,
      otherConditions: [
        { conditionTypeCode: "RS003", startValue: "5000" },
      ],
    };
    const xml = buildCouponIssueXml(c);
    expect(xml).toContain("<otherConditions>");
    expect(xml).toContain("<conditionTypeCode>RS003</conditionTypeCode>");
    expect(xml).toContain("<startValue>5000</startValue>");
  });
});

describe("buildCouponUpdateXml", () => {
  it("includes couponCode element", () => {
    const xml = buildCouponUpdateXml({
      ...minimalCoupon,
      couponCode: "UPDATEME",
    });
    expect(xml).toContain("<couponUpdateRequest>");
    expect(xml).toContain("<couponCode>UPDATEME</couponCode>");
  });
});

describe("buildCouponDeleteXml", () => {
  it("builds delete request with coupon code", () => {
    const xml = buildCouponDeleteXml({ couponCode: "DELME" });
    expect(xml).toContain("<couponDeleteRequest>");
    expect(xml).toContain("<couponCode>DELME</couponCode>");
  });
});
