/**
 * Shared DTOs used across all Rakuten RMS API endpoints.
 * Ported from JakeJP/Rakuten.RMS.Api — REST/XML/ResultBase.cs and error models.
 */

/** Status block returned in every RMS API response envelope. */
export interface RakutenStatus {
  /** API interface identifier */
  interfaceId: string;
  /** System status: "OK" or "NG" */
  systemStatus: "OK" | "NG";
  /** Human-readable status message */
  message: string;
  /** Unique request ID for support tracing */
  requestId: string;
}

/** A single error entry from the RMS API. */
export interface RakutenApiError {
  /** Machine-readable error code (e.g., "COUPON-001") */
  code: string;
  /** Human-readable error message in Japanese */
  message: string;
  /** Optional metadata such as the offending property path */
  metadata?: Record<string, string>;
}

/** Result of parsing an error response. */
export interface ErrorParseResult {
  status?: RakutenStatus;
  errors: RakutenApiError[];
}

/**
 * Generic search condition shared by coupon and thanks coupon searches.
 * Specific search DTOs extend this with their own filter fields.
 */
export interface SearchCondition {
  /** Number of results per page (default varies by endpoint, max ~100-200) */
  hits?: number;
  /** Page number (1-indexed) */
  page?: number;
  /** Additional filter fields — endpoint-specific */
  [key: string]: unknown;
}

/** Paginated response wrapper. */
export interface PaginatedResponse<T> {
  /** Total count of matching items across all pages */
  allCount: number;
  /** Items on the current page */
  items: T[];
}
