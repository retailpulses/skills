import assert from "node:assert/strict";
import { validatePriceUpdateInput } from "./rakuten_rms_price_playwright.mjs";

const valid = {
  shopId: "123456",
  managementNumber: "item-001",
  newPrice: 57680,
};

assert.equal(validatePriceUpdateInput(valid).commit, false);
assert.equal(validatePriceUpdateInput(valid).taxIncluded, true);
assert.equal(validatePriceUpdateInput({ ...valid, taxIncluded: false }).taxIncluded, false);
assert.equal(validatePriceUpdateInput({ ...valid, commit: true }).commit, true);
assert.throws(() => validatePriceUpdateInput({ ...valid, shopId: "shop" }), /numeric/);
assert.throws(() => validatePriceUpdateInput({ ...valid, managementNumber: "", searchKeyword: "" }), /required/);
assert.throws(() => validatePriceUpdateInput({ ...valid, newPrice: 0 }), /positive/);
assert.throws(() => validatePriceUpdateInput({ ...valid, newPrice: 57.68 }), /integer/);
assert.throws(() => validatePriceUpdateInput({ ...valid, taxIncluded: "yes" }), /boolean/);

console.log("Rakuten RMS price input validation tests passed.");
