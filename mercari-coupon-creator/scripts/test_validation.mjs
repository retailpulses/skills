import assert from "node:assert/strict";
import { validateCouponInput } from "./mercari_coupon_playwright.mjs";

const valid = {
  shopId: "SHOP123",
  productCodes: ["ITEM001"],
  discountType: "amount",
  discountValue: 200,
  issueCount: 10,
  singleUsePerBuyer: false,
  startAt: "2026-06-21T08:00:00+09:00",
  endAt: "2026-06-25T23:00:00+09:00",
};

assert.equal(validateCouponInput(valid).commit, false);
assert.throws(() => validateCouponInput({ ...valid, productCodes: ["ITEM001", "ITEM001"] }), /duplicates/);
assert.throws(() => validateCouponInput({ ...valid, endAt: "2026-08-01T23:00:00+09:00" }), /30 days/);
assert.throws(() => validateCouponInput({ ...valid, startAt: "2026-06-21T08:00:00Z" }), /JST/);
assert.throws(() => validateCouponInput({ ...valid, issueCount: 0 }), /positive integer/);

console.log("Coupon input validation tests passed.");
