/**
 * Thanks Coupon DTOs for Rakuten RMS ThanksCouponAPI.
 *
 * Thanks coupons are automatically granted to customers who meet specific
 * conditions (total purchase price, grant period, service use history).
 * Unlike standard coupons which are claimed via URL, thanks coupons are
 * auto-issued by Rakuten's system.
 *
 * All thanks coupon endpoints use XML serialization over /es/1.0/thankscoupon* paths.
 *
 * Ported from JakeJP/Rakuten.RMS.Api — CouponAPI/ThanksCouponToIssue.cs
 */

import type {
  CombineFlag,
  ConditionTypeCode,
  DiscountType,
  GetCondCd,
  IssueStatus,
} from "../types.js";
import type { PaginatedResponse } from "./common.js";

// ─── Other conditions (applied to coupon usage) ─────────────────

/** Additional usage condition for a thanks coupon. */
export interface ThanksOtherCondition {
  /**
   * Condition type code.
   * RS001 = device (0=PC, 1=Mobile)
   * RS002 = sales method (0=Normal)
   * RS003 = minimum amount (yen)
   * RS004 = minimum quantity
   */
  conditionTypeCode: ConditionTypeCode | string;
  /** Start/max value for the condition */
  startValue: string;
}

// ─── Auto-get conditions (criteria for granting the coupon) ─────

/**
 * Condition that determines when a thanks coupon is automatically granted.
 *
 * At minimum, "totalPrice" and "grantTerm" are required.
 * "serviceUseHistory" is optional.
 */
export interface ThanksAutoGetCondition {
  /**
   * Condition type:
   * - "totalPrice" (required): minimum purchase price to trigger grant
   * - "grantTerm" (required): period during which purchases count
   * - "serviceUseHistory" (optional): service use history requirement
   */
  getCondCd: GetCondCd | string;
  /** Start value for the condition */
  startValue: string;
  /** End value for the condition (optional) */
  endValue?: string;
  /** Comparison operator code (optional) */
  compOperatorCd?: string;
}

// ─── ThanksCouponToIssue (creation/update payload) ──────────────

/**
 * Payload for creating or updating a thanks coupon.
 */
export interface ThanksCouponToIssue {
  /** Coupon image URL (optional) */
  couponImage?: string;

  /**
   * Coupon name / title.
   * Max 50 characters.
   */
  couponName: string;

  /**
   * Coupon caption / short description.
   * Max 30 characters.
   */
  couponCaption: string;

  /**
   * Discount type.
   * 1 = fixed amount (yen), 2 = percentage, 4 = free shipping
   */
  discountType: DiscountType;

  /**
   * Discount value.
   * For fixed amount: the amount in yen.
   * For percentage: the percentage (e.g., 10 = 10%).
   */
  discountFactor: number;

  /**
   * Period (in days) during which the coupon cannot be used
   * relative to the grant date. Optional.
   */
  couponUnavailableTerm?: number;

  /**
   * Validity period of the coupon in days from the grant date.
   * Required.
   */
  couponTerm: number;

  /**
   * Maximum number of times a single member can use this coupon.
   * Required.
   */
  memberAvailMaxCount: number;

  /**
   * Whether this coupon can be combined with other coupons.
   * 0 = cannot combine, 1 = can combine
   */
  combineFlag: CombineFlag;

  /**
   * Additional usage conditions (device, sales method, amount, quantity).
   * Optional.
   */
  thanksOtherConditions?: ThanksOtherCondition[];

  /**
   * Auto-grant conditions — criteria for automatically issuing this coupon.
   * Must include at least "totalPrice" and "grantTerm".
   * Optional: "serviceUseHistory".
   */
  thanksAutoGetConditions?: ThanksAutoGetCondition[];
}

// ─── ThanksCoupon (full entity) ─────────────────────────────────

/**
 * Full thanks coupon entity including system-assigned fields.
 * Returned by search/get endpoints.
 */
export interface ThanksCoupon extends ThanksCouponToIssue {
  /** Unique thanks coupon ID assigned by Rakuten */
  thanksCouponId: number;
  /** Shop ID */
  shopId: number;
  /** Shop name */
  shopName: string;
  /** Shop URL on Rakuten Ichiba */
  shopUrl: string;
}

// ─── Search condition ───────────────────────────────────────────

/** Search/query parameters for finding thanks coupons. */
export interface SearchThanksCouponCondition {
  /**
   * Filter by issue status:
   * 3 = before distribution period
   * 4 = currently being distributed
   * 5 = manually stopped
   * 6 = distribution period ended
   */
  issueStatus?: IssueStatus;
  /** Filter coupons granted on or after this date */
  grantStartDate?: string;
  /** Filter coupons granted on or before this date */
  grantEndDate?: string;
  /** Registration date filter */
  regDate?: string;
  /** Number of results per page (max 100, default 30) */
  hits?: number;
  /** Page number (1-indexed, default 1) */
  page?: number;
}

/** Response from a thanks coupon search query. */
export interface ThanksCouponSearchResponse extends PaginatedResponse<ThanksCoupon> {
  /** Alias for items — the thanks coupons on this page */
  thanksCoupons: ThanksCoupon[];
}

// ─── Validators ─────────────────────────────────────────────────

/** Result of a field validation. */
export interface ValidationResult {
  valid: boolean;
  message?: string;
}

function fail(message: string): ValidationResult {
  return { valid: false, message };
}

/** Validate a ThanksCouponToIssue payload. */
export function validateThanksCouponToIssue(
  coupon: ThanksCouponToIssue,
): ValidationResult[] {
  const results: ValidationResult[] = [];

  if (!coupon.couponName || coupon.couponName.trim().length === 0) {
    results.push(fail("couponName is required."));
  } else if (coupon.couponName.length > 50) {
    results.push(fail(`couponName must be ≤ 50 characters (got ${coupon.couponName.length}).`));
  }

  if (!coupon.couponCaption || coupon.couponCaption.trim().length === 0) {
    results.push(fail("couponCaption is required."));
  } else if (coupon.couponCaption.length > 30) {
    results.push(fail(`couponCaption must be ≤ 30 characters (got ${coupon.couponCaption.length}).`));
  }

  if (typeof coupon.discountFactor !== "number" || isNaN(coupon.discountFactor)) {
    results.push(fail("discountFactor is required and must be a number."));
  } else if (coupon.discountType === 1 && coupon.discountFactor < 1) {
    results.push(fail("Fixed discount must be ≥ 1 yen."));
  } else if (coupon.discountType === 2 && (coupon.discountFactor < 1 || coupon.discountFactor > 99)) {
    results.push(fail("Percentage discount must be 1-99."));
  }

  if (!coupon.couponTerm || coupon.couponTerm < 1) {
    results.push(fail("couponTerm is required and must be ≥ 1 day."));
  }

  if (!coupon.memberAvailMaxCount || coupon.memberAvailMaxCount < 1) {
    results.push(fail("memberAvailMaxCount is required and must be ≥ 1."));
  }

  // Auto-get conditions: at least totalPrice and grantTerm should be present
  const autoGetConds = coupon.thanksAutoGetConditions ?? [];
  const hasTotalPrice = autoGetConds.some((c) => c.getCondCd === "totalPrice");
  const hasGrantTerm = autoGetConds.some((c) => c.getCondCd === "grantTerm");
  if (!hasTotalPrice) {
    results.push(fail('thanksAutoGetConditions must include "totalPrice".'));
  }
  if (!hasGrantTerm) {
    results.push(fail('thanksAutoGetConditions must include "grantTerm".'));
  }

  return results;
}
