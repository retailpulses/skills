/**
 * RakutenPromotionClient — the main entry point for Rakuten RMS Promotion APIs.
 *
 * This is an API-first client: all Rakuten-specific concerns (ESA auth,
 * XML serialization, rate limiting, retry, error parsing) are handled here.
 * Business logic should never call the RMS API directly — it should go through
 * a repository that uses this client, per the CLAUDE.md Repository/Adapter pattern.
 *
 * Ported from JakeJP/Rakuten.RMS.Api — ServiceProvider.cs (auth) and
 * REST/XML/RakutenApiXmlClientBase.cs (HTTP dispatch).
 *
 * Usage:
 *   import { createPromotionClient } from "./rakuten-promotion-api";
 *
 *   const client = createPromotionClient({
 *     serviceSecret: env.RAKUTEN_SERVICE_SECRET,
 *     licenseKey: env.RAKUTEN_LICENSE_KEY,
 *   });
 *
 *   const result = await client.coupon.issue({ couponName: "...", ... });
 */

import { buildAuthHeader } from "./auth.js";
import { RateLimiter, withRetry, DEFAULT_RETRY_CONFIG } from "./retry.js";
import type { RetryConfig } from "./retry.js";
import { handleErrorResponse } from "./parser/error.js";
import { RMS_BASE_URL } from "./types.js";
import {
  couponIssue,
  couponUpdate,
  couponDelete,
  couponGet,
  couponSearch,
  couponSearchAll,
} from "./endpoints/coupon.js";
import type { HttpDispatcher } from "./endpoints/coupon.js";
import {
  thanksCouponIssue,
  thanksCouponUpdate,
  thanksCouponStop,
  thanksCouponGet,
  thanksCouponSearch,
  thanksCouponSearchAll,
} from "./endpoints/thanks-coupon.js";

// ─── Client options ─────────────────────────────────────────────

/** Configuration for creating a RakutenPromotionClient. */
export interface RakutenPromotionClientOptions {
  /** RMS service secret from WEB API Service settings */
  serviceSecret: string;
  /** RMS license key from WEB API Service settings (expires every 90 days) */
  licenseKey: string;
  /** Base URL override (default: https://api.rms.rakuten.co.jp) */
  baseUrl?: string;
  /** Retry configuration (default: 3 attempts, 1s base backoff, 30s max) */
  retryConfig?: Partial<RetryConfig>;
  /** Minimum delay between requests in ms (default: 1000 = 1 req/sec) */
  rateLimitDelayMs?: number;
  /** Dry-run mode: log requests without sending them */
  dryRun?: boolean;
}

// ─── Public client interface ────────────────────────────────────

/** Typed interface for the Coupon sub-client. */
export interface CouponClient {
  issue: (input: Parameters<typeof couponIssue>[1]) => ReturnType<typeof couponIssue>;
  update: (coupon: Parameters<typeof couponUpdate>[1]) => ReturnType<typeof couponUpdate>;
  delete: (req: Parameters<typeof couponDelete>[1]) => ReturnType<typeof couponDelete>;
  get: (couponCode: string) => ReturnType<typeof couponGet>;
  search: (condition?: Parameters<typeof couponSearch>[1]) => ReturnType<typeof couponSearch>;
  searchAll: (condition?: Parameters<typeof couponSearch>[1]) => ReturnType<typeof couponSearchAll>;
}

/** Typed interface for the ThanksCoupon sub-client. */
export interface ThanksCouponClient {
  issue: (input: Parameters<typeof thanksCouponIssue>[1]) => ReturnType<typeof thanksCouponIssue>;
  update: (id: number, input: Parameters<typeof thanksCouponUpdate>[2]) => ReturnType<typeof thanksCouponUpdate>;
  stop: (id: number) => ReturnType<typeof thanksCouponStop>;
  get: (id: number) => ReturnType<typeof thanksCouponGet>;
  search: (condition?: Parameters<typeof thanksCouponSearch>[1]) => ReturnType<typeof thanksCouponSearch>;
  searchAll: (condition?: Parameters<typeof thanksCouponSearch>[1]) => ReturnType<typeof thanksCouponSearchAll>;
}

/** The complete Rakuten Promotion API client. */
export interface RakutenPromotionClient {
  coupon: CouponClient;
  thanksCoupon: ThanksCouponClient;
}

// ─── Factory ────────────────────────────────────────────────────

/**
 * Create a Rakuten Promotion API client.
 *
 * The client handles:
 * - ESA authentication header construction
 * - Rate limiting (1 req/sec default)
 * - Automatic retry with exponential backoff
 * - XML request/response serialization
 * - Error parsing and typed error throwing
 * - Dry-run mode for safe testing
 */
export function createPromotionClient(
  options: RakutenPromotionClientOptions,
): RakutenPromotionClient {
  const baseUrl = options.baseUrl ?? RMS_BASE_URL;
  const authHeader = buildAuthHeader({
    serviceSecret: options.serviceSecret,
    licenseKey: options.licenseKey,
  });
  const rateLimiter = new RateLimiter(
    options.rateLimitDelayMs ?? 1000,
  );
  const retryConfig: RetryConfig = {
    ...DEFAULT_RETRY_CONFIG,
    ...options.retryConfig,
  };
  const dryRun = options.dryRun ?? false;

  /**
   * Internal HTTP dispatcher.
   * Every endpoint method calls this to make HTTP requests.
   * It applies: rate limiting → auth header → retry → error handling.
   */
  const dispatch: HttpDispatcher = async (method, path, reqOptions = {}) => {
    const url = new URL(path, baseUrl);

    // Add query parameters
    if (reqOptions.query) {
      for (const [key, value] of Object.entries(reqOptions.query)) {
        if (value !== undefined) {
          url.searchParams.set(key, value);
        }
      }
    }

    const headers: Record<string, string> = {
      Authorization: authHeader,
      Accept: "application/xml, application/json",
    };

    if (reqOptions.body && reqOptions.contentType) {
      headers["Content-Type"] = reqOptions.contentType;
    }

    const fetchInit: RequestInit = {
      method,
      headers,
    };

    if (reqOptions.body) {
      fetchInit.body = reqOptions.body;
    }

    // Dry-run: log and return a fake success response
    if (dryRun) {
      console.log(
        `[DRY-RUN] ${method} ${url.toString()}`,
        reqOptions.body ? `\nBody: ${reqOptions.body.slice(0, 500)}` : "",
      );
      return new Response("<result><status><systemStatus>OK</systemStatus></status></result>", {
        status: 200,
        headers: { "content-type": "application/xml" },
      });
    }

    // Execute with rate limiting and retry
    return withRetry(
      async () => {
        await rateLimiter.waitIfNeeded();
        const response = await fetch(url.toString(), fetchInit);

        if (!response.ok) {
          const context = `${method} ${path}`;
          await handleErrorResponse(response, context);
        }

        return response;
      },
      retryConfig,
    );
  };

  // Build sub-clients by binding dispatch to endpoint modules
  return {
    coupon: {
      issue: (input) => couponIssue(dispatch, input),
      update: (coupon) => couponUpdate(dispatch, coupon),
      delete: (req) => couponDelete(dispatch, req),
      get: (couponCode) => couponGet(dispatch, couponCode),
      search: (condition) => couponSearch(dispatch, condition),
      searchAll: (condition) => couponSearchAll(dispatch, condition),
    },
    thanksCoupon: {
      issue: (input) => thanksCouponIssue(dispatch, input),
      update: (id, input) => thanksCouponUpdate(dispatch, id, input),
      stop: (id) => thanksCouponStop(dispatch, id),
      get: (id) => thanksCouponGet(dispatch, id),
      search: (condition) => thanksCouponSearch(dispatch, condition),
      searchAll: (condition) => thanksCouponSearchAll(dispatch, condition),
    },
  };
}
