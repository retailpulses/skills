/**
 * Coupon API endpoint dispatchers.
 *
 * Handles the wire-level HTTP communication for all 6 coupon operations:
 * issue, update, delete, get, search, searchAll.
 *
 * All coupon endpoints use XML serialization and the /es/1.0/coupon/* path prefix.
 * Ported from JakeJP/Rakuten.RMS.Api — CouponAPI/CouponAPI.cs
 */

import { API_V1 } from "../types.js";
import type {
  Coupon,
  CouponToIssue,
  IssuedCoupon,
  CouponSearchCondition,
  CouponSearchResponse,
  CouponDeleteRequest,
} from "../dto/coupon.js";
import {
  buildCouponIssueXml,
  buildCouponUpdateXml,
  buildCouponDeleteXml,
  parseXmlResponse,
} from "../parser/xml.js";
import { extractInlineErrors, RakutenPromotionError } from "../parser/error.js";

/** Signature for the internal HTTP dispatch function injected by the client. */
export type HttpDispatcher = (
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  options?: {
    body?: string;
    contentType?: string;
    query?: Record<string, string | undefined>;
  },
) => Promise<Response>;

// ─── Issue ──────────────────────────────────────────────────────

/**
 * Issue (create) a new coupon.
 * POST /es/1.0/coupon/issue
 */
export async function couponIssue(
  dispatch: HttpDispatcher,
  input: CouponToIssue,
): Promise<IssuedCoupon> {
  const xml = buildCouponIssueXml(input);
  const response = await dispatch("POST", `${API_V1}/coupon/issue`, {
    body: xml,
    contentType: "application/xml; charset=utf-8",
  });

  const body = await response.text();
  const parsed = parseXmlResponse<{
    result?: {
      couponIssueResult?: {
        couponCode?: string;
        pcGetUrl?: string;
      };
    };
  }>(body);

  // Check for inline errors in success HTTP response
  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Coupon issue failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }

  const result = parsed.result?.couponIssueResult;
  if (!result?.couponCode) {
    throw new RakutenPromotionError({
      message: "Coupon issue returned no coupon code.",
      errors: [{ code: "NO_COUPON_CODE", message: "Response missing couponCode" }],
      httpStatus: response.status,
    });
  }

  return {
    couponCode: result.couponCode,
    pcGetUrl: result.pcGetUrl ?? "",
  };
}

// ─── Update ─────────────────────────────────────────────────────

/**
 * Update an existing coupon.
 * POST /es/1.0/coupon/update
 */
export async function couponUpdate(
  dispatch: HttpDispatcher,
  coupon: CouponToIssue & { couponCode: string },
): Promise<void> {
  if (!coupon.couponCode) {
    throw new RakutenPromotionError({
      message: "couponCode is required for update.",
      errors: [{ code: "MISSING_COUPON_CODE", message: "couponCode is required" }],
      httpStatus: 400,
    });
  }

  const xml = buildCouponUpdateXml(coupon);
  const response = await dispatch("POST", `${API_V1}/coupon/update`, {
    body: xml,
    contentType: "application/xml; charset=utf-8",
  });

  const body = await response.text();
  const parsed = parseXmlResponse<unknown>(body);
  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Coupon update failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }
}

// ─── Delete ─────────────────────────────────────────────────────

/**
 * Delete a coupon by its code.
 * POST /es/1.0/coupon/delete
 */
export async function couponDelete(
  dispatch: HttpDispatcher,
  req: CouponDeleteRequest,
): Promise<void> {
  if (!req.couponCode) {
    throw new RakutenPromotionError({
      message: "couponCode is required for delete.",
      errors: [{ code: "MISSING_COUPON_CODE", message: "couponCode is required" }],
      httpStatus: 400,
    });
  }

  const xml = buildCouponDeleteXml(req);
  await dispatch("POST", `${API_V1}/coupon/delete`, {
    body: xml,
    contentType: "application/xml; charset=utf-8",
  });
}

// ─── Get (single) ───────────────────────────────────────────────

/**
 * Get a single coupon by its code.
 * GET /es/1.0/coupon/search?couponCode=...
 *
 * Note: The RMS API uses the search endpoint with couponCode filter
 * for single-coupon retrieval per the reference .NET library.
 */
export async function couponGet(
  dispatch: HttpDispatcher,
  couponCode: string,
): Promise<Coupon | null> {
  const response = await dispatch("GET", `${API_V1}/coupon/search`, {
    query: { couponCode },
  });

  if (response.status === 404) return null;

  const body = await response.text();
  const parsed = parseXmlResponse<{
    result?: {
      coupons?: {
        coupon?: Coupon | Coupon[];
      };
    };
  }>(body);

  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Coupon get failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }

  const coupons = parsed.result?.coupons?.coupon;
  if (!coupons) return null;

  const list = Array.isArray(coupons) ? coupons : [coupons];
  return list[0] ?? null;
}

// ─── Search ─────────────────────────────────────────────────────

/**
 * Search for coupons with optional filters.
 * GET /es/1.0/coupon/search
 */
export async function couponSearch(
  dispatch: HttpDispatcher,
  condition: CouponSearchCondition = {},
): Promise<CouponSearchResponse> {
  const query: Record<string, string | undefined> = {};

  if (condition.couponName) query.couponName = condition.couponName;
  if (condition.couponCode) query.couponCode = condition.couponCode;
  if (condition.itemUrl) query.itemUrl = condition.itemUrl;
  if (condition.couponStartDate) query.couponStartDate = condition.couponStartDate;
  if (condition.couponEndDate) query.couponEndDate = condition.couponEndDate;
  if (condition.hits !== undefined) query.hits = String(condition.hits);
  if (condition.page !== undefined) query.page = String(condition.page);

  const response = await dispatch("GET", `${API_V1}/coupon/search`, { query });

  const body = await response.text();
  const parsed = parseXmlResponse<{
    result?: {
      allCount?: string;
      coupons?: {
        coupon?: Coupon | Coupon[];
      };
    };
  }>(body);

  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Coupon search failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }

  const result = parsed.result;
  const allCount = parseInt(result?.allCount ?? "0", 10);
  const rawCoupons = result?.coupons?.coupon;
  const coupons: Coupon[] = rawCoupons
    ? (Array.isArray(rawCoupons) ? rawCoupons : [rawCoupons])
    : [];

  return { allCount, coupons, items: coupons };
}

// ─── SearchAll (auto-paginated) ─────────────────────────────────

/**
 * Auto-paginating search — iterates through all pages of coupons.
 * Yields coupons one page at a time via async iterator.
 *
 * Usage:
 *   for await (const page of couponSearchAll(client.dispatch, condition)) {
 *     for (const coupon of page.coupons) { ... }
 *   }
 */
export async function* couponSearchAll(
  dispatch: HttpDispatcher,
  condition: CouponSearchCondition = {},
): AsyncGenerator<CouponSearchResponse> {
  let page = condition.page ?? 1;
  const hits = condition.hits ?? 100;
  let totalFetched = 0;

  while (true) {
    const result = await couponSearch(dispatch, { ...condition, page, hits });
    yield result;

    totalFetched += result.coupons.length;
    if (totalFetched >= result.allCount || result.coupons.length === 0) {
      break;
    }
    page++;
  }
}
