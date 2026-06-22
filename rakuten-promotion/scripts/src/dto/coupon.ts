/**
 * Coupon DTOs for Rakuten RMS CouponAPI.
 *
 * Ported from JakeJP/Rakuten.RMS.Api — CouponAPI/Models.cs and CouponAPI/CouponAPI.cs
 * All coupon endpoints use XML serialization over the /es/1.0/coupon/* paths.
 *
 * XML envelope:
 *   Request:  <request><couponIssueRequest><coupon>...</coupon></couponIssueRequest></request>
 *   Response: <result><status/><errors/><coupon>...</coupon></result>
 */

import type {
  CombineFlag,
  ConditionTypeCode,
  DiscountType,
  DisplayFlag,
  ItemType,
  RankCode,
} from "../types.js";
import type { PaginatedResponse, SearchCondition } from "./common.js";

// ─── Item reference ────────────────────────────────────────────

/** A target item for a coupon (referenced by item URL). */
export interface CouponItem {
  /** Item page URL on Rakuten Ichiba */
  itemUrl: string;
}

// ─── Other conditions ───────────────────────────────────────────

/** Additional usage condition for a coupon. */
export interface OtherCondition {
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

// ─── Rank-based targeting ───────────────────────────────────────

/** Member rank condition for targeted coupons. */
export interface RankCondition {
  /** Gender targeting: 0=unspecified, 1=male, 2=female */
  gender?: 0 | 1 | 2;
  /** Age targeting */
  age?: number;
  /** Prefecture code for geographic targeting */
  prefecture?: string;
  /** Member rank code: 0=none, 1=Regular, 2=Silver, 3=Gold, 4=Platinum, 5=Diamond */
  rankCode?: RankCode;
}

// ─── CouponToIssue (creation payload) ───────────────────────────

/**
 * Payload for creating (issuing) a new coupon.
 * This is the primary DTO — all fields map to XML elements.
 */
export interface CouponToIssue {
  /**
   * Coupon name / title.
   * Max 50 characters.
   */
  couponName: string;

  /**
   * Coupon caption / short description shown to customers.
   * Max 30 characters.
   */
  couponCaption: string;

  /**
   * Coupon validity start date in ISO 8601 format.
   * Must include time and JST offset: "2026-06-18T00:00:00+09:00"
   */
  couponStartDate: string;

  /**
   * Coupon validity end date in ISO 8601 format.
   * Must include time and JST offset: "2026-07-18T23:59:59+09:00"
   */
  couponEndDate: string;

  /** Coupon image URL (optional). C# name: couponImage */
  couponImage?: string;

  /**
   * Number of coupons to issue.
   * Must be >= 1.
   * C# name: issueCount
   */
  issueCount: number;

  /**
   * Target item type.
   * 1 = single item, 3 = multiple items, 4 = entire order, 5 = free shipping
   */
  itemType: ItemType;

  /**
   * Discount type.
   * 1 = fixed amount (yen), 2 = percentage, 4 = free shipping
   */
  discountType: DiscountType;

  /**
   * Discount value.
   * For fixed amount: the amount in yen.
   * For percentage: the percentage (e.g., 10 = 10%).
   * For free shipping: ignored.
   */
  discountFactor: number;

  /**
   * Maximum number of times a single member can use this coupon.
   * Default: 1
   * C# name: memberAvailMaxCount
   */
  memberAvailMaxCount?: number;

  /** Rank-based targeting conditions (optional). */
  rankCondition?: RankCondition;

  /**
   * Whether this coupon can be combined with other coupons.
   * 0 = cannot combine, 1 = can combine
   */
  combineFlag: CombineFlag;

  /**
   * Whether to display this coupon on the shop page.
   * 0 = hidden, 1 = visible. Default: 1
   */
  displayFlag?: DisplayFlag;

  /**
   * Target items. Required when itemType is 1 or 3.
   * Max 3000 items per coupon.
   */
  items?: CouponItem[];

  /**
   * Additional usage conditions (device, sales method, amount, quantity).
   * Optional.
   */
  otherConditions?: OtherCondition[];
}

// ─── Coupon (full entity with code) ─────────────────────────────

/**
 * Full coupon entity including the issued coupon code.
 * Returned by search/get and used for updates.
 */
export interface Coupon extends CouponToIssue {
  /** Unique coupon code (assigned by Rakuten on issue) */
  couponCode: string;
}

// ─── Issued coupon response ─────────────────────────────────────

/** Response from a successful coupon issue operation. */
export interface IssuedCoupon {
  /** The issued coupon code */
  couponCode: string;
  /** PC-accessible URL to obtain the coupon */
  pcGetUrl: string;
}

// ─── Coupon search ──────────────────────────────────────────────

/** Search/query parameters for finding coupons. */
export interface CouponSearchCondition extends SearchCondition {
  /** Filter by coupon name (partial match) */
  couponName?: string;
  /** Filter by exact coupon code */
  couponCode?: string;
  /** Filter by target item URL */
  itemUrl?: string;
  /** Filter coupons active on or after this date */
  couponStartDate?: string;
  /** Filter coupons active on or before this date */
  couponEndDate?: string;
}

/** Response from a coupon search query. */
export interface CouponSearchResponse extends PaginatedResponse<Coupon> {
  /** Alias for items — the coupons on this page */
  coupons: Coupon[];
}

// ─── Coupon delete ──────────────────────────────────────────────

/** Request payload for deleting a coupon. */
export interface CouponDeleteRequest {
  couponCode: string;
}

// ─── Validators ─────────────────────────────────────────────────

/** Result of a field validation. */
export interface ValidationResult {
  valid: boolean;
  message?: string;
}

function ok(): ValidationResult {
  return { valid: true };
}
function fail(message: string): ValidationResult {
  return { valid: false, message };
}

/** Validate coupon name length (max 50 chars). */
export function validateCouponName(name: string): ValidationResult {
  if (!name || name.trim().length === 0) return fail("Coupon name is required.");
  if (name.length > 50) return fail(`Coupon name must be ≤ 50 characters (got ${name.length}).`);
  return ok();
}

/** Validate coupon caption length (max 30 chars). */
export function validateCouponCaption(caption: string): ValidationResult {
  if (!caption || caption.trim().length === 0) return fail("Coupon caption is required.");
  if (caption.length > 30) return fail(`Coupon caption must be ≤ 30 characters (got ${caption.length}).`);
  return ok();
}

/** Validate discount factor based on discount type. */
export function validateDiscountFactor(
  discountType: DiscountType,
  factor: number,
): ValidationResult {
  if (typeof factor !== "number" || isNaN(factor)) return fail("Discount factor is required.");
  if (discountType === 1) {
    // Fixed amount: must be >= 1 yen
    if (factor < 1) return fail("Fixed discount must be ≥ 1 yen.");
    if (factor > 999999) return fail("Fixed discount too large.");
  } else if (discountType === 2) {
    // Percentage: 1-99
    if (factor < 1 || factor > 99) return fail("Percentage discount must be 1-99.");
  }
  // Free shipping (4): factor is ignored
  return ok();
}

/** Validate that start date is before end date. */
export function validateDateRange(
  start: string,
  end: string,
): ValidationResult {
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (isNaN(startDate.getTime())) return fail("Invalid start date.");
  if (isNaN(endDate.getTime())) return fail("Invalid end date.");
  if (startDate >= endDate) return fail("Start date must be before end date.");
  return ok();
}

/**
 * Validate an entire CouponToIssue payload.
 * Returns array of all validation failures, or empty array if valid.
 */
export function validateCouponToIssue(coupon: CouponToIssue): ValidationResult[] {
  const results: ValidationResult[] = [];
  const checks = [
    validateCouponName(coupon.couponName),
    validateCouponCaption(coupon.couponCaption),
    validateDiscountFactor(coupon.discountType, coupon.discountFactor),
    validateDateRange(coupon.couponStartDate, coupon.couponEndDate),
  ];

  for (const r of checks) {
    if (!r.valid) results.push(r);
  }

  // Issue count must be >= 1
  if (coupon.issueCount < 1) {
    results.push(fail("issueCount must be ≥ 1."));
  }

  // Items required for single-item and multi-item types
  if (
    (coupon.itemType === 1 || coupon.itemType === 3) &&
    (!coupon.items || coupon.items.length === 0)
  ) {
    results.push(fail("Items are required when itemType is 1 (single) or 3 (multiple)."));
  }

  // Max 3000 items
  if (coupon.items && coupon.items.length > 3000) {
    results.push(fail(`Max 3000 items per coupon (got ${coupon.items.length}).`));
  }

  return results;
}
