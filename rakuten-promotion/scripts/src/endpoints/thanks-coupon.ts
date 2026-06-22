/**
 * Thanks Coupon API endpoint dispatchers.
 *
 * Thanks coupons are automatically granted to customers meeting specific conditions.
 * Unlike standard coupons (which use POST for all mutating operations), thanks coupons
 * use proper RESTful verbs (POST for create, PUT for update/stop, GET for read).
 *
 * All thanks coupon endpoints use XML serialization and the /es/1.0/thankscoupon* paths.
 * Ported from JakeJP/Rakuten.RMS.Api — CouponAPI/CouponAPI.cs (thanks coupon methods).
 */

import { API_V1 } from "../types.js";
import type {
  ThanksCouponToIssue,
  ThanksCoupon,
  SearchThanksCouponCondition,
  ThanksCouponSearchResponse,
} from "../dto/thanks-coupon.js";
import { parseXmlResponse } from "../parser/xml.js";
import { extractInlineErrors, RakutenPromotionError } from "../parser/error.js";
import { escapeXml, XML_HEADER } from "../parser/xml.js";
import type { HttpDispatcher } from "./coupon.js";

// ─── XML builders (inline — smaller structures than standard coupons) ───

function buildThanksCouponXml(input: ThanksCouponToIssue): string {
  const lines: string[] = [];
  lines.push(XML_HEADER);
  lines.push("<request>");
  lines.push("  <thanksCoupon>");

  lines.push(`    <couponName>${escapeXml(input.couponName)}</couponName>`);
  lines.push(`    <couponCaption>${escapeXml(input.couponCaption)}</couponCaption>`);
  lines.push(`    <discountType>${input.discountType}</discountType>`);
  lines.push(`    <discountFactor>${input.discountFactor}</discountFactor>`);
  lines.push(`    <couponTerm>${input.couponTerm}</couponTerm>`);
  lines.push(`    <memberAvailMaxCount>${input.memberAvailMaxCount}</memberAvailMaxCount>`);
  lines.push(`    <combineFlag>${input.combineFlag}</combineFlag>`);

  if (input.couponImage) {
    lines.push(`    <couponImage>${escapeXml(input.couponImage)}</couponImage>`);
  }
  if (input.couponUnavailableTerm !== undefined) {
    lines.push(`    <couponUnavailableTerm>${input.couponUnavailableTerm}</couponUnavailableTerm>`);
  }

  // Other conditions
  if (input.thanksOtherConditions && input.thanksOtherConditions.length > 0) {
    lines.push("    <thanksOtherConditions>");
    for (const cond of input.thanksOtherConditions) {
      lines.push("      <thanksOtherCondition>");
      lines.push(`        <conditionTypeCode>${escapeXml(cond.conditionTypeCode)}</conditionTypeCode>`);
      lines.push(`        <startValue>${escapeXml(cond.startValue)}</startValue>`);
      lines.push("      </thanksOtherCondition>");
    }
    lines.push("    </thanksOtherConditions>");
  }

  // Auto-get conditions
  if (input.thanksAutoGetConditions && input.thanksAutoGetConditions.length > 0) {
    lines.push("    <thanksAutoGetConditions>");
    for (const cond of input.thanksAutoGetConditions) {
      lines.push("      <thanksAutoGetCondition>");
      lines.push(`        <getCondCd>${escapeXml(cond.getCondCd)}</getCondCd>`);
      lines.push(`        <startValue>${escapeXml(cond.startValue)}</startValue>`);
      if (cond.endValue) {
        lines.push(`        <endValue>${escapeXml(cond.endValue)}</endValue>`);
      }
      if (cond.compOperatorCd) {
        lines.push(`        <compOperatorCd>${escapeXml(cond.compOperatorCd)}</compOperatorCd>`);
      }
      lines.push("      </thanksAutoGetCondition>");
    }
    lines.push("    </thanksAutoGetConditions>");
  }

  lines.push("  </thanksCoupon>");
  lines.push("</request>");

  return lines.join("\n");
}

// ─── Issue ──────────────────────────────────────────────────────

/**
 * Issue (create) a new thanks coupon.
 * POST /es/1.0/thankscoupon
 *
 * @returns The created thanks coupon ID
 */
export async function thanksCouponIssue(
  dispatch: HttpDispatcher,
  input: ThanksCouponToIssue,
): Promise<number> {
  const xml = buildThanksCouponXml(input);
  const response = await dispatch("POST", `${API_V1}/thankscoupon`, {
    body: xml,
    contentType: "application/xml; charset=utf-8",
  });

  const body = await response.text();
  const parsed = parseXmlResponse<{
    result?: {
      thanksCouponId?: string;
    };
  }>(body);

  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Thanks coupon issue failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }

  const id = parseInt(parsed.result?.thanksCouponId ?? "0", 10);
  if (!id) {
    throw new RakutenPromotionError({
      message: "Thanks coupon issue returned no ID.",
      errors: [{ code: "NO_ID", message: "Response missing thanksCouponId" }],
      httpStatus: response.status,
    });
  }

  return id;
}

// ─── Update ─────────────────────────────────────────────────────

/**
 * Update an existing thanks coupon.
 * PUT /es/1.0/thankscoupon/{id}
 *
 * @param id — The thanks coupon ID to update
 * @param input — Partial or full update payload
 * @returns The thanks coupon ID
 */
export async function thanksCouponUpdate(
  dispatch: HttpDispatcher,
  id: number,
  input: Partial<ThanksCouponToIssue>,
): Promise<number> {
  // Merge input with defaults for required fields not provided
  const full: ThanksCouponToIssue = {
    couponName: input.couponName ?? "",
    couponCaption: input.couponCaption ?? "",
    discountType: input.discountType ?? 1,
    discountFactor: input.discountFactor ?? 0,
    couponTerm: input.couponTerm ?? 30,
    memberAvailMaxCount: input.memberAvailMaxCount ?? 1,
    combineFlag: input.combineFlag ?? 0,
    ...input,
  };

  const xml = buildThanksCouponXml(full);
  const response = await dispatch("PUT", `${API_V1}/thankscoupon/${id}`, {
    body: xml,
    contentType: "application/xml; charset=utf-8",
  });

  const body = await response.text();
  const parsed = parseXmlResponse<unknown>(body);
  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Thanks coupon update failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }

  return id;
}

// ─── Stop ───────────────────────────────────────────────────────

/**
 * Stop a thanks coupon (end distribution early).
 * PUT /es/1.0/thankscoupon/{id}/issuestatus/stop
 *
 * @param id — The thanks coupon ID to stop
 * @returns The thanks coupon ID
 */
export async function thanksCouponStop(
  dispatch: HttpDispatcher,
  id: number,
): Promise<number> {
  const response = await dispatch(
    "PUT",
    `${API_V1}/thankscoupon/${id}/issuestatus/stop`,
  );

  const body = await response.text();
  const parsed = parseXmlResponse<unknown>(body);
  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Thanks coupon stop failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }

  return id;
}

// ─── Get ────────────────────────────────────────────────────────

/**
 * Get a single thanks coupon by ID.
 * GET /es/1.0/thankscoupon/{id}
 *
 * @returns The thanks coupon, or null if not found
 */
export async function thanksCouponGet(
  dispatch: HttpDispatcher,
  id: number,
): Promise<ThanksCoupon | null> {
  const response = await dispatch("GET", `${API_V1}/thankscoupon/${id}`);

  if (response.status === 404) return null;

  const body = await response.text();
  const parsed = parseXmlResponse<{
    result?: {
      thanksCoupon?: ThanksCoupon;
    };
  }>(body);

  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Thanks coupon get failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }

  return parsed.result?.thanksCoupon ?? null;
}

// ─── Search ─────────────────────────────────────────────────────

/**
 * Search for thanks coupons with optional filters.
 * GET /es/1.0/thankscoupon
 *
 * Note: Returns null when there are no results (404 behavior per reference lib).
 *
 * @returns Search response, or null if no results
 */
export async function thanksCouponSearch(
  dispatch: HttpDispatcher,
  condition: SearchThanksCouponCondition = {},
): Promise<ThanksCouponSearchResponse | null> {
  const query: Record<string, string | undefined> = {};

  if (condition.issueStatus !== undefined) query.issueStatus = String(condition.issueStatus);
  if (condition.grantStartDate) query.grantStartDate = condition.grantStartDate;
  if (condition.grantEndDate) query.grantEndDate = condition.grantEndDate;
  if (condition.regDate) query.regDate = condition.regDate;
  if (condition.hits !== undefined) query.hits = String(condition.hits);
  if (condition.page !== undefined) query.page = String(condition.page);

  const response = await dispatch("GET", `${API_V1}/thankscoupon`, { query });

  // 404 means no results (documented oddity)
  if (response.status === 404) return null;

  const body = await response.text();
  const parsed = parseXmlResponse<{
    result?: {
      allCount?: string;
      thanksCoupons?: {
        thanksCoupon?: ThanksCoupon | ThanksCoupon[];
      };
    };
  }>(body);

  const inlineErrors = extractInlineErrors(parsed);
  if (inlineErrors.length > 0) {
    throw new RakutenPromotionError({
      message: `Thanks coupon search failed: ${inlineErrors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`,
      errors: inlineErrors,
      httpStatus: response.status,
    });
  }

  const result = parsed.result;
  const allCount = parseInt(result?.allCount ?? "0", 10);
  const rawCoupons = result?.thanksCoupons?.thanksCoupon;
  const thanksCoupons: ThanksCoupon[] = rawCoupons
    ? (Array.isArray(rawCoupons) ? rawCoupons : [rawCoupons])
    : [];

  return { allCount, thanksCoupons, items: thanksCoupons };
}

// ─── SearchAll (auto-paginated) ─────────────────────────────────

/**
 * Auto-paginating search — iterates through all pages of thanks coupons.
 * Handles the 404-on-empty-results behavior correctly.
 *
 * Usage:
 *   for await (const page of thanksCouponSearchAll(client.dispatch, condition)) {
 *     for (const coupon of page.thanksCoupons) { ... }
 *   }
 */
export async function* thanksCouponSearchAll(
  dispatch: HttpDispatcher,
  condition: SearchThanksCouponCondition = {},
): AsyncGenerator<ThanksCouponSearchResponse> {
  let page = condition.page ?? 1;
  const hits = condition.hits ?? 30;
  let totalFetched = 0;

  while (true) {
    const result = await thanksCouponSearch(dispatch, { ...condition, page, hits });

    if (!result || result.thanksCoupons.length === 0) {
      break;
    }

    yield result;
    totalFetched += result.thanksCoupons.length;

    if (totalFetched >= result.allCount) {
      break;
    }
    page++;
  }
}
