/**
 * Rakuten Promotion API — TypeScript client for Rakuten RMS Coupon & Thanks Coupon APIs.
 *
 * API-first design: this client is the canonical interface to Rakuten RMS promotions.
 * Use it standalone in Cloudflare Workers, Node.js VPS, or any JS runtime with fetch().
 *
 * Ported from JakeJP/Rakuten.RMS.Api (MIT license) — authentication, endpoints,
 * DTOs, validation, and error handling. Adds retry + rate limiting (missing from .NET lib).
 *
 * ## Quick Start
 *
 * ```ts
 * import { createPromotionClient } from "rakuten-promotion-api";
 *
 * const client = createPromotionClient({
 *   serviceSecret: process.env.RAKUTEN_SERVICE_SECRET,
 *   licenseKey: process.env.RAKUTEN_LICENSE_KEY,
 * });
 *
 * // Issue a 10% off coupon
 * const result = await client.coupon.issue({
 *   couponName: "夏のセール10%オフ",
 *   couponCaption: "全品10%割引",
 *   couponStartDate: "2026-07-01T00:00:00+09:00",
 *   couponEndDate: "2026-07-31T23:59:59+09:00",
 *   issueCount: 1000,
 *   itemType: 4,      // entire order
 *   discountType: 2,  // percentage
 *   discountFactor: 10,
 *   combineFlag: 0,
 *   displayFlag: 1,
 * });
 *
 * console.log(`Issued: ${result.couponCode} — ${result.pcGetUrl}`);
 * ```
 *
 * ## Repository/Adapter Pattern
 *
 * Per CLAUDE.md, wrap this client in an adapter:
 *
 * ```ts
 * // adapters/rakuten-promotion.ts
 * import { createPromotionClient } from "rakuten-promotion-api";
 * export function createAdapter(env: Env) {
 *   const client = createPromotionClient({ serviceSecret: env.RAKUTEN_SERVICE_SECRET, licenseKey: env.RAKUTEN_LICENSE_KEY });
 *   return { issueCoupon: (p) => client.coupon.issue(p), ... };
 * }
 *
 * // repositories/promotion.ts
 * import { createAdapter } from "../adapters/rakuten-promotion";
 * export function createPromotionRepo(env: Env) {
 *   const adapter = createAdapter(env);
 *   return { activateSeasonalPromotion: async (products, pct) => { ... } };
 * }
 * ```
 *
 * @module rakuten-promotion-api
 */

// Client factory
export { createPromotionClient } from "./client.js";
export type {
  RakutenPromotionClient,
  RakutenPromotionClientOptions,
  CouponClient,
  ThanksCouponClient,
} from "./client.js";

// Auth utilities
export { buildAuthHeader, readCredentials, maskCredential } from "./auth.js";
export type { RakutenCredentials } from "./auth.js";

// Retry + rate limiting
export { RateLimiter, withRetry, isRetryableError, DEFAULT_RETRY_CONFIG, DEFAULT_RATE_LIMIT_DELAY_MS } from "./retry.js";
export type { RetryConfig } from "./retry.js";

// Type enums
export {
  DiscountType,
  ItemType,
  IssueStatus,
  GenderCond,
  RankCode,
  ConditionTypeCode,
  GetCondCd,
  CombineFlag,
  DisplayFlag,
  RMS_BASE_URL,
  API_V1,
} from "./types.js";

// Coupon DTOs + validators
export type {
  CouponToIssue,
  Coupon,
  IssuedCoupon,
  CouponItem,
  OtherCondition,
  RankCondition,
  CouponSearchCondition,
  CouponSearchResponse,
  CouponDeleteRequest,
  ValidationResult,
} from "./dto/coupon.js";
export {
  validateCouponName,
  validateCouponCaption,
  validateDiscountFactor,
  validateDateRange,
  validateCouponToIssue,
} from "./dto/coupon.js";

// Thanks Coupon DTOs + validators
export type {
  ThanksCouponToIssue,
  ThanksCoupon,
  ThanksOtherCondition,
  ThanksAutoGetCondition,
  SearchThanksCouponCondition,
  ThanksCouponSearchResponse,
} from "./dto/thanks-coupon.js";
export { validateThanksCouponToIssue } from "./dto/thanks-coupon.js";

// Common DTOs
export type {
  RakutenApiError,
  RakutenStatus,
  ErrorParseResult,
  SearchCondition,
  PaginatedResponse,
} from "./dto/common.js";

// Error handling
export { RakutenPromotionError, parseErrorXml, parseErrorJson, extractInlineErrors, handleErrorResponse } from "./parser/error.js";
