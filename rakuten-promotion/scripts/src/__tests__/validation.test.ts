/**
 * Tests for coupon and thanks coupon validators.
 */
import { describe, it, expect } from "vitest";
import {
  validateCouponName,
  validateCouponCaption,
  validateDiscountFactor,
  validateDateRange,
  validateCouponToIssue,
} from "../dto/coupon.js";
import { validateThanksCouponToIssue } from "../dto/thanks-coupon.js";
import type { CouponToIssue } from "../dto/coupon.js";
import type { ThanksCouponToIssue } from "../dto/thanks-coupon.js";

describe("validateCouponName", () => {
  it("accepts valid names", () => {
    expect(validateCouponName("サマーセール").valid).toBe(true);
  });

  it("rejects empty name", () => {
    expect(validateCouponName("").valid).toBe(false);
  });

  it("rejects whitespace-only name", () => {
    expect(validateCouponName("   ").valid).toBe(false);
  });

  it("rejects name over 50 chars", () => {
    expect(validateCouponName("あ".repeat(51)).valid).toBe(false);
  });

  it("accepts exactly 50 chars", () => {
    expect(validateCouponName("あ".repeat(50)).valid).toBe(true);
  });
});

describe("validateCouponCaption", () => {
  it("accepts valid captions", () => {
    expect(validateCouponCaption("全品10%OFF").valid).toBe(true);
  });

  it("rejects empty caption", () => {
    expect(validateCouponCaption("").valid).toBe(false);
  });

  it("rejects caption over 30 chars", () => {
    expect(validateCouponCaption("あ".repeat(31)).valid).toBe(false);
  });
});

describe("validateDiscountFactor", () => {
  it("accepts fixed discount >= 1", () => {
    expect(validateDiscountFactor(1, 500).valid).toBe(true);
  });

  it("rejects fixed discount < 1", () => {
    expect(validateDiscountFactor(1, 0).valid).toBe(false);
  });

  it("accepts percentage 1-99", () => {
    expect(validateDiscountFactor(2, 10).valid).toBe(true);
    expect(validateDiscountFactor(2, 1).valid).toBe(true);
    expect(validateDiscountFactor(2, 99).valid).toBe(true);
  });

  it("rejects percentage outside 1-99", () => {
    expect(validateDiscountFactor(2, 0).valid).toBe(false);
    expect(validateDiscountFactor(2, 100).valid).toBe(false);
  });

  it("accepts free shipping with any factor", () => {
    // free shipping ignores the factor
    expect(validateDiscountFactor(4, 0).valid).toBe(true);
    expect(validateDiscountFactor(4, 999).valid).toBe(true);
  });

  it("rejects NaN", () => {
    expect(validateDiscountFactor(1, NaN).valid).toBe(false);
  });
});

describe("validateDateRange", () => {
  it("accepts valid range", () => {
    expect(
      validateDateRange("2026-07-01T00:00:00+09:00", "2026-07-31T23:59:59+09:00").valid,
    ).toBe(true);
  });

  it("rejects end before start", () => {
    expect(
      validateDateRange("2026-07-31T00:00:00+09:00", "2026-07-01T00:00:00+09:00").valid,
    ).toBe(false);
  });

  it("rejects equal dates", () => {
    expect(
      validateDateRange("2026-07-01T00:00:00+09:00", "2026-07-01T00:00:00+09:00").valid,
    ).toBe(false);
  });

  it("rejects invalid date strings", () => {
    expect(validateDateRange("not-a-date", "2026-07-01T00:00:00+09:00").valid).toBe(false);
  });
});

const validCoupon: CouponToIssue = {
  couponName: "テストクーポン",
  couponCaption: "テスト用",
  couponStartDate: "2026-07-01T00:00:00+09:00",
  couponEndDate: "2026-07-31T23:59:59+09:00",
  issueCount: 100,
  itemType: 4,
  discountType: 2,
  discountFactor: 10,
  combineFlag: 0,
};

describe("validateCouponToIssue", () => {
  it("accepts a valid coupon", () => {
    expect(validateCouponToIssue(validCoupon)).toEqual([]);
  });

  it("reports all validation errors", () => {
    const badCoupon: CouponToIssue = {
      ...validCoupon,
      couponName: "",
      discountFactor: 0,
    };
    const errors = validateCouponToIssue(badCoupon);
    expect(errors.length).toBeGreaterThanOrEqual(2);
  });

  it("requires items when itemType is 1 (single item)", () => {
    const c: CouponToIssue = { ...validCoupon, itemType: 1, items: [] };
    const errors = validateCouponToIssue(c);
    expect(errors.some((e) => e.message?.includes("Items are required"))).toBe(true);
  });

  it("rejects more than 3000 items", () => {
    const items = Array.from({ length: 3001 }, (_, i) => ({
      itemUrl: `https://item.rakuten.co.jp/shop/${i}/`,
    }));
    const c: CouponToIssue = { ...validCoupon, itemType: 1, items };
    const errors = validateCouponToIssue(c);
    expect(errors.some((e) => e.message?.includes("3000"))).toBe(true);
  });
});

describe("validateThanksCouponToIssue", () => {
  const validThanks: ThanksCouponToIssue = {
    couponName: "ご愛顧クーポン",
    couponCaption: "次回10%OFF",
    discountType: 2,
    discountFactor: 10,
    couponTerm: 30,
    memberAvailMaxCount: 1,
    combineFlag: 0,
    thanksAutoGetConditions: [
      { getCondCd: "totalPrice", startValue: "10000" },
      { getCondCd: "grantTerm", startValue: "2026-06-01T00:00:00+09:00", endValue: "2026-06-30T23:59:59+09:00" },
    ],
  };

  it("accepts a valid thanks coupon", () => {
    expect(validateThanksCouponToIssue(validThanks)).toEqual([]);
  });

  it("requires totalPrice in auto-get conditions", () => {
    const c = {
      ...validThanks,
      thanksAutoGetConditions: [
        { getCondCd: "grantTerm" as const, startValue: "2026-06-01T00:00:00+09:00" },
      ],
    };
    const errors = validateThanksCouponToIssue(c);
    expect(errors.some((e) => e.message?.includes("totalPrice"))).toBe(true);
  });

  it("requires grantTerm in auto-get conditions", () => {
    const c = {
      ...validThanks,
      thanksAutoGetConditions: [
        { getCondCd: "totalPrice" as const, startValue: "10000" },
      ],
    };
    const errors = validateThanksCouponToIssue(c);
    expect(errors.some((e) => e.message?.includes("grantTerm"))).toBe(true);
  });

  it("requires couponTerm >= 1", () => {
    const c = { ...validThanks, couponTerm: 0 };
    const errors = validateThanksCouponToIssue(c);
    expect(errors.some((e) => e.message?.includes("couponTerm"))).toBe(true);
  });
});
