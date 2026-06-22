/**
 * Retry and rate-limiting utilities for Rakuten RMS API.
 *
 * The .NET reference library (JakeJP/Rakuten.RMS.Api) has NO retry or rate-limit
 * logic — every request is attempted exactly once. This module adds:
 *
 * 1. Per-client rate limiting (default 1 req/sec, configurable)
 * 2. Exponential backoff with jitter on retryable failures
 * 3. Sensible defaults for which errors are retryable
 */

/** Configuration for retry behavior. */
export interface RetryConfig {
  /** Maximum number of attempts (including the first). Default: 3 */
  maxAttempts: number;
  /** Base backoff in milliseconds. Default: 1000 */
  baseBackoffMs: number;
  /** Maximum backoff cap in milliseconds. Default: 30000 */
  maxBackoffMs: number;
}

export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxAttempts: 3,
  baseBackoffMs: 1000,
  maxBackoffMs: 30_000,
};

/** Default rate-limit delay: 1 request per second. */
export const DEFAULT_RATE_LIMIT_DELAY_MS = 1000;

/**
 * Shape of an error that carries HTTP status information.
 * Both Response objects and RakutenPromotionError implement this.
 */
interface HttpErrorLike {
  httpStatus?: number;
  retryable?: boolean;
  status?: number;
}

/**
 * Determine whether an error is retryable.
 * Retryable: 429 (rate limit), 5xx (server errors), network/fetch errors,
 * and any error explicitly marked as retryable.
 * Not retryable: other 4xx client errors.
 */
export function isRetryableError(err: unknown): boolean {
  // RakutenPromotionError with explicit retryable flag
  const httpErr = err as HttpErrorLike;
  if (httpErr.retryable === true) return true;
  // HTTP 429 (Response object from fetch)
  if (httpErr.status === 429) return true;
  if (httpErr.httpStatus === 429) return true;
  // HTTP 5xx server errors
  if (httpErr.status !== undefined && httpErr.status >= 500 && httpErr.status < 600) return true;
  if (httpErr.httpStatus !== undefined && httpErr.httpStatus >= 500 && httpErr.httpStatus < 600) return true;
  // Network errors (TypeError from fetch) are retryable
  if (err instanceof TypeError) return true;
  return false;
}

/**
 * Compute exponential backoff delay with jitter.
 * Formula: min(baseBackoffMs * 2^(attempt-1) + jitter, maxBackoffMs)
 * Jitter is ±10% of the computed base delay.
 */
export function computeBackoff(
  attempt: number,
  config: RetryConfig = DEFAULT_RETRY_CONFIG,
): number {
  const baseDelay = config.baseBackoffMs * Math.pow(2, attempt - 1);
  const jitter = Math.floor(baseDelay * 0.1 * (Math.random() * 2 - 1));
  return Math.min(baseDelay + jitter, config.maxBackoffMs);
}

/** Sleep for a given number of milliseconds. */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Execute a function with retry logic.
 *
 * @param fn — The async function to execute
 * @param config — Retry configuration
 * @param retryable — Optional custom predicate to determine if an error is retryable
 * @returns The result of fn()
 * @throws The last error if all attempts are exhausted
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  config: RetryConfig = DEFAULT_RETRY_CONFIG,
  retryable: (err: unknown) => boolean = isRetryableError,
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= config.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (attempt >= config.maxAttempts || !retryable(err)) {
        throw err;
      }
      const delay = computeBackoff(attempt, config);
      await sleep(delay);
    }
  }

  throw lastError;
}

/**
 * Simple rate limiter that enforces a minimum delay between requests.
 * Tracks the timestamp of the last request and waits if needed.
 */
export class RateLimiter {
  private lastRequestTime = 0;
  private delayMs: number;

  constructor(delayMs: number = DEFAULT_RATE_LIMIT_DELAY_MS) {
    this.delayMs = delayMs;
  }

  /** Wait until the rate limit allows another request. */
  async waitIfNeeded(): Promise<void> {
    const now = Date.now();
    const elapsed = now - this.lastRequestTime;
    if (elapsed < this.delayMs) {
      await sleep(this.delayMs - elapsed);
    }
    this.lastRequestTime = Date.now();
  }
}

