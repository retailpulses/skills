/**
 * Error parsing and exception classes for Rakuten RMS API.
 *
 * Rakuten RMS returns errors in two forms:
 * 1. HTTP-level errors (4xx/5xx) with XML or JSON error bodies
 * 2. Success-level HTTP responses (200) with <errors> in the XML body
 *
 * This module parses both forms into a typed RakutenPromotionError.
 *
 * Ported from JakeJP/Rakuten.RMS.Api — REST/XML/ErrorResponseException.cs
 * and REST/JSON/ErrorResponseException.cs
 */

import type { RakutenApiError, RakutenStatus } from "../dto/common.js";
import { parseXmlResponse } from "./xml.js";

// ─── Error class ────────────────────────────────────────────────

/**
 * Typed error for Rakuten RMS API failures.
 * Carries parsed error details, HTTP status, and whether the error is retryable.
 */
export class RakutenPromotionError extends Error {
  /** Individual error entries from the API response */
  public readonly errors: RakutenApiError[];
  /** API status block (if present in response) */
  public readonly status?: RakutenStatus;
  /** HTTP status code */
  public readonly httpStatus: number;
  /** Whether this error is safe to retry */
  public readonly retryable: boolean;

  constructor(params: {
    message: string;
    errors?: RakutenApiError[];
    status?: RakutenStatus;
    httpStatus: number;
    retryable?: boolean;
  }) {
    super(params.message);
    this.name = "RakutenPromotionError";
    this.errors = params.errors ?? [];
    this.status = params.status;
    this.httpStatus = params.httpStatus;
    this.retryable = params.retryable ?? isRetryableHttpStatus(params.httpStatus);
  }

  /** Human-readable summary of all errors. */
  get errorSummary(): string {
    if (this.errors.length === 0) return this.message;
    return this.errors
      .map((e) => `[${e.code}] ${e.message}`)
      .join("; ");
  }
}

// ─── Retryable status check ─────────────────────────────────────

function isRetryableHttpStatus(status: number): boolean {
  return status === 429 || (status >= 500 && status < 600);
}

// ─── XML error parsing ──────────────────────────────────────────

/** Shape of a raw XML error response from the RMS API. */
interface RawXmlErrorResult {
  result?: {
    status?: {
      interfaceId?: string;
      systemStatus?: string;
      message?: string;
      requestId?: string;
    };
    errors?: {
      error?: RawXmlError | RawXmlError[];
    };
  };
}

interface RawXmlError {
  code?: string;
  message?: string;
}

/**
 * Parse an XML error response body into structured errors.
 *
 * Expected XML structure:
 *   <result>
 *     <status>
 *       <interfaceId>...</interfaceId>
 *       <systemStatus>NG</systemStatus>
 *       <message>...</message>
 *       <requestId>...</requestId>
 *     </status>
 *     <errors>
 *       <error>
 *         <code>...</code>
 *         <message>...</message>
 *       </error>
 *     </errors>
 *   </result>
 */
export function parseErrorXml(xml: string): {
  status?: RakutenStatus;
  errors: RakutenApiError[];
} {
  try {
    const raw = parseXmlResponse<RawXmlErrorResult>(xml);
    // fast-xml-parser doesn't throw on invalid XML; check for meaningful structure
    if (!raw || typeof raw !== "object" || !raw.result) {
      return {
        errors: [{ code: "PARSE_ERROR", message: `Unparseable or empty XML response: ${xml.slice(0, 200)}` }],
      };
    }
    const result = raw.result;
    if (!result) return { errors: [] };

    // Parse status
    const status: RakutenStatus | undefined = result.status
      ? {
          interfaceId: result.status.interfaceId ?? "",
          systemStatus: (result.status.systemStatus === "OK" ? "OK" : "NG") as "OK" | "NG",
          message: result.status.message ?? "",
          requestId: result.status.requestId ?? "",
        }
      : undefined;

    // Parse errors array
    const rawErrors = result.errors?.error;
    const errors: RakutenApiError[] = [];
    if (rawErrors) {
      const errorList = Array.isArray(rawErrors) ? rawErrors : [rawErrors];
      for (const e of errorList) {
        errors.push({
          code: e.code ?? "UNKNOWN",
          message: e.message ?? "Unknown error",
        });
      }
    }

    return { status, errors };
  } catch {
    // If XML parsing fails, return the raw text as a single error
    return {
      errors: [{ code: "PARSE_ERROR", message: `Failed to parse error response: ${xml.slice(0, 500)}` }],
    };
  }
}

// ─── JSON error parsing ─────────────────────────────────────────

/** Shape of a raw JSON error response (used by ItemAPI 2.0, ItemBundleAPI, etc.). */
interface RawJsonErrorResult {
  errors?: RawJsonErrorEntry[];
}

interface RawJsonErrorEntry {
  code?: string;
  message?: string;
  metadata?: Record<string, string>;
}

/**
 * Parse a JSON error response body into structured errors.
 *
 * Expected JSON structure:
 *   { "errors": [{ "code": "...", "message": "...", "metadata": { "propertyPath": "..." } }] }
 */
export function parseErrorJson(json: string): {
  errors: RakutenApiError[];
} {
  try {
    const raw: RawJsonErrorResult = JSON.parse(json);
    const errors: RakutenApiError[] = (raw.errors ?? []).map((e) => ({
      code: e.code ?? "UNKNOWN",
      message: e.message ?? "Unknown error",
      metadata: e.metadata,
    }));
    return { errors };
  } catch {
    return {
      errors: [{ code: "PARSE_ERROR", message: `Failed to parse error response: ${json.slice(0, 500)}` }],
    };
  }
}

// ─── Response validation ────────────────────────────────────────

/** Shape of a parsed XML result envelope with optional status and errors. */
interface ResultEnvelope {
  result?: {
    status?: {
      systemStatus?: string;
      message?: string;
      interfaceId?: string;
      requestId?: string;
    };
    errors?: {
      error?: RawXmlError | RawXmlError[];
    };
  };
}

/**
 * Check a parsed XML result for inline error markers.
 * Some RMS endpoints return HTTP 200 but with <systemStatus>NG</systemStatus>
 * and <errors> in the body. This catches those cases.
 *
 * @returns Array of RakutenApiError if errors found, empty array otherwise.
 */
export function extractInlineErrors(parsed: unknown): RakutenApiError[] {
  const envelope = parsed as ResultEnvelope;
  if (!envelope?.result) return [];

  const status = envelope.result.status;
  const rawErrors = envelope.result.errors?.error;

  // If systemStatus is NG but no explicit errors, create one from status message
  if (status?.systemStatus === "NG" && !rawErrors) {
    return [
      {
        code: "SYSTEM_NG",
        message: status.message ?? "System status NG — no additional error details",
      },
    ];
  }

  if (rawErrors) {
    const errorList = Array.isArray(rawErrors) ? rawErrors : [rawErrors];
    return errorList.map((e) => ({
      code: e.code ?? "UNKNOWN",
      message: e.message ?? "Unknown error",
    }));
  }

  return [];
}

// ─── HTTP response error handler ────────────────────────────────

/**
 * Process an HTTP response that indicates an error.
 * Reads the body, detects XML vs JSON, parses errors, and throws RakutenPromotionError.
 *
 * @param response — The fetch Response object
 * @param context — Human-readable context for the error message (e.g., "issuing coupon")
 * @throws RakutenPromotionError always
 */
export async function handleErrorResponse(
  response: Response,
  context: string,
): Promise<never> {
  const httpStatus = response.status;
  const contentType = response.headers.get("content-type") ?? "";
  const body = await response.text();

  let errors: RakutenApiError[] = [];
  let status: RakutenStatus | undefined;

  if (contentType.includes("xml") || body.trimStart().startsWith("<?xml")) {
    const parsed = parseErrorXml(body);
    errors = parsed.errors;
    status = parsed.status;
  } else if (contentType.includes("json") || body.trimStart().startsWith("{")) {
    const parsed = parseErrorJson(body);
    errors = parsed.errors;
  }

  const message =
    errors.length > 0
      ? `Error ${context}: ${errors.map((e) => `[${e.code}] ${e.message}`).join("; ")}`
      : `Error ${context}: HTTP ${httpStatus} — ${body.slice(0, 300)}`;

  throw new RakutenPromotionError({
    message,
    errors,
    status,
    httpStatus,
  });
}
