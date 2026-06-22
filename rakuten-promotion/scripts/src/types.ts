/**
 * Enums and type constants for Rakuten RMS Promotion APIs.
 * Ported from JakeJP/Rakuten.RMS.Api — CouponAPI and ThanksCouponAPI models.
 */

/** Discount type for coupons and thanks coupons. */
export const DiscountType = {
  /** Fixed amount off (yen) */
  Flat: 1,
  /** Percentage off */
  Percentage: 2,
  /** Free shipping */
  FreeShipping: 4,
} as const;
export type DiscountType = (typeof DiscountType)[keyof typeof DiscountType];

/** Target item type for standard coupons. */
export const ItemType = {
  /** Single specific item */
  SingleItem: 1,
  /** Multiple specific items */
  MultipleItems: 3,
  /** Entire order */
  Order: 4,
  /** Free shipping (item type for shipping coupons) */
  FreeShipping: 5,
} as const;
export type ItemType = (typeof ItemType)[keyof typeof ItemType];

/** Issue status filter for thanks coupon search. */
export const IssueStatus = {
  /** Before distribution period */
  BeforePeriod: 3,
  /** Currently being distributed */
  InPeriod: 4,
  /** Manually stopped */
  Stopped: 5,
  /** Distribution period ended */
  Ended: 6,
} as const;
export type IssueStatus = (typeof IssueStatus)[keyof typeof IssueStatus];

/** Gender targeting condition. */
export const GenderCond = {
  Unspecified: 0,
  Male: 1,
  Female: 2,
} as const;
export type GenderCond = (typeof GenderCond)[keyof typeof GenderCond];

/** Member rank condition codes. */
export const RankCode = {
  None: 0,
  Regular: 1,
  Silver: 2,
  Gold: 3,
  Platinum: 4,
  Diamond: 5,
} as const;
export type RankCode = (typeof RankCode)[keyof typeof RankCode];

/** Other condition type codes for coupon restrictions. */
export const ConditionTypeCode = {
  /** Device specification: startValue 0=PC, 1=Mobile */
  Device: "RS001",
  /** Sales method: startValue 0=Normal purchase */
  SalesMethod: "RS002",
  /** Minimum usage amount (yen): startValue 1-999999999 */
  UsageAmount: "RS003",
  /** Minimum usage quantity (items): startValue 0-999999999 */
  UsageQuantity: "RS004",
} as const;
export type ConditionTypeCode = (typeof ConditionTypeCode)[keyof typeof ConditionTypeCode];

/** Auto-get condition codes for thanks coupons. */
export const GetCondCd = {
  /** Total purchase price condition (required) */
  TotalPrice: "totalPrice",
  /** Grant period condition (required) */
  GrantTerm: "grantTerm",
  /** Service use history condition (optional) */
  ServiceUseHistory: "serviceUseHistory",
} as const;
export type GetCondCd = (typeof GetCondCd)[keyof typeof GetCondCd];

/** Combine flag — whether coupon can be combined with other coupons. */
export const CombineFlag = {
  /** Cannot be combined */
  NoCombine: 0,
  /** Can be combined */
  CanCombine: 1,
} as const;
export type CombineFlag = (typeof CombineFlag)[keyof typeof CombineFlag];

/** Display flag — whether to show the coupon on the shop page. */
export const DisplayFlag = {
  Hidden: 0,
  Visible: 1,
} as const;
export type DisplayFlag = (typeof DisplayFlag)[keyof typeof DisplayFlag];

/** Base URL for Rakuten RMS API. */
export const RMS_BASE_URL = "https://api.rms.rakuten.co.jp";

/** API version path prefixes. */
export const API_V1 = "/es/1.0";
