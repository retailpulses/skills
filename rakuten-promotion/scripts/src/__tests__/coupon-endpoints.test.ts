/**
 * Integration-shaped tests for coupon endpoints with mocked HTTP dispatch.
 */
import { describe, it, expect } from "vitest";
import {
  couponIssue,
  couponGet,
  couponSearch,
  couponDelete,
} from "../endpoints/coupon.js";
import type { HttpDispatcher } from "../endpoints/coupon.js";
import { RakutenPromotionError } from "../parser/error.js";
import type { CouponToIssue, Coupon } from "../dto/coupon.js";

/** Read a fixture file synchronously (tests run in Node via Vitest). */
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

function fixture(name: string): string {
  return readFileSync(resolve(__dirname, "fixtures", name), "utf-8");
}

/** Create a mock dispatcher that returns a fixed Response. */
function mockDispatch(response: Response): HttpDispatcher {
  return async () => response;
}

/** Create a mock dispatcher from fixture XML + status. */
function mockDispatchXml(
  fixtureName: string,
  status = 200,
  contentType = "application/xml; charset=utf-8",
): HttpDispatcher {
  const body = fixture(fixtureName);
  return mockDispatch(
    new Response(body, { status, headers: { "content-type": contentType } }),
  );
}

const validCoupon: CouponToIssue = {
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

describe("couponIssue", () => {
  it("issues a coupon and returns code + URL", async () => {
    const dispatch = mockDispatchXml("coupon-issue-response.xml");
    const result = await couponIssue(dispatch, validCoupon);
    expect(result.couponCode).toBe("ABC123DEF456");
    expect(result.pcGetUrl).toBe("https://coupon.rakuten.co.jp/get/ABC123DEF456");
  });

  it("throws on error XML response", async () => {
    const dispatch = mockDispatchXml("coupon-error-response.xml", 400);
    await expect(couponIssue(dispatch, validCoupon)).rejects.toThrow(
      RakutenPromotionError,
    );
  });
});

describe("couponGet", () => {
  it("returns coupon by code", async () => {
    const dispatch = mockDispatchXml("coupon-search-response.xml");
    const result = await couponGet(dispatch, "COUPON001");
    expect(result).not.toBeNull();
    expect(result!.couponCode).toBe("COUPON001");
    expect(result!.couponName).toBe("テストクーポン1");
  });

  it("returns null on 404", async () => {
    const dispatch = mockDispatch(
      new Response("Not Found", { status: 404 }),
    );
    const result = await couponGet(dispatch, "NONEXISTENT");
    expect(result).toBeNull();
  });
});

describe("couponSearch", () => {
  it("searches and returns paginated results", async () => {
    const dispatch = mockDispatchXml("coupon-search-response.xml");
    const result = await couponSearch(dispatch, {});
    expect(result.allCount).toBe(2);
    expect(result.coupons).toHaveLength(2);
    expect(result.items).toHaveLength(2);
    expect(result.coupons[0].couponCode).toBe("COUPON001");
    expect(result.coupons[1].couponCode).toBe("COUPON002");
  });
});

describe("couponDelete", () => {
  it("deletes without error on success", async () => {
    const successXml = fixture("coupon-issue-response.xml"); // reuse: any success envelope works
    const dispatch = mockDispatch(
      new Response(successXml, {
        status: 200,
        headers: { "content-type": "application/xml" },
      }),
    );
    await expect(
      couponDelete(dispatch, { couponCode: "DELME" }),
    ).resolves.toBeUndefined();
  });

  it("throws when couponCode is empty", async () => {
    const dispatch = mockDispatch(new Response("", { status: 200 }));
    await expect(
      couponDelete(dispatch, { couponCode: "" }),
    ).rejects.toThrow("couponCode is required");
  });
});
