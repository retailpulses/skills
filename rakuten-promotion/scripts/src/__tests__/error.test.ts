/**
 * Tests for error parsing and RakutenPromotionError class.
 */
import { describe, it, expect } from "vitest";
import {
  RakutenPromotionError,
  parseErrorXml,
  parseErrorJson,
  extractInlineErrors,
} from "../parser/error.js";
import { parseXmlResponse } from "../parser/xml.js";

describe("RakutenPromotionError", () => {
  it("constructs with all fields", () => {
    const err = new RakutenPromotionError({
      message: "Something went wrong",
      errors: [{ code: "E001", message: "Error detail" }],
      httpStatus: 400,
      retryable: false,
    });

    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(RakutenPromotionError);
    expect(err.name).toBe("RakutenPromotionError");
    expect(err.message).toBe("Something went wrong");
    expect(err.errors).toHaveLength(1);
    expect(err.httpStatus).toBe(400);
    expect(err.retryable).toBe(false);
  });

  it("auto-sets retryable from HTTP status", () => {
    const retryable429 = new RakutenPromotionError({
      message: "Rate limited",
      errors: [],
      httpStatus: 429,
    });
    expect(retryable429.retryable).toBe(true);

    const retryable500 = new RakutenPromotionError({
      message: "Server error",
      errors: [],
      httpStatus: 500,
    });
    expect(retryable500.retryable).toBe(true);

    const notRetryable = new RakutenPromotionError({
      message: "Bad request",
      errors: [],
      httpStatus: 400,
    });
    expect(notRetryable.retryable).toBe(false);
  });

  it("errorSummary joins error codes and messages", () => {
    const err = new RakutenPromotionError({
      message: "Multiple errors",
      errors: [
        { code: "E001", message: "First error" },
        { code: "E002", message: "Second error" },
      ],
      httpStatus: 400,
    });
    expect(err.errorSummary).toBe("[E001] First error; [E002] Second error");
  });

  it("errorSummary falls back to message when no errors", () => {
    const err = new RakutenPromotionError({
      message: "Plain error",
      errors: [],
      httpStatus: 500,
    });
    expect(err.errorSummary).toBe("Plain error");
  });
});

describe("parseErrorXml", () => {
  it("parses error XML with status and errors", () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<result>
  <status>
    <interfaceId>coupon.issue</interfaceId>
    <systemStatus>NG</systemStatus>
    <message>Validation error</message>
    <requestId>req-123</requestId>
  </status>
  <errors>
    <error>
      <code>COUPON-001</code>
      <message>Name too long</message>
    </error>
    <error>
      <code>COUPON-003</code>
      <message>Invalid date</message>
    </error>
  </errors>
</result>`;

    const result = parseErrorXml(xml);
    expect(result.status?.systemStatus).toBe("NG");
    expect(result.status?.message).toBe("Validation error");
    expect(result.errors).toHaveLength(2);
    expect(result.errors[0].code).toBe("COUPON-001");
    expect(result.errors[1].code).toBe("COUPON-003");
  });

  it("handles single error element (not array)", () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<result>
  <errors>
    <error>
      <code>SINGLE</code>
      <message>Just one</message>
    </error>
  </errors>
</result>`;

    const result = parseErrorXml(xml);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].code).toBe("SINGLE");
  });

  it("handles unparseable XML gracefully", () => {
    const result = parseErrorXml("not xml at all");
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].code).toBe("PARSE_ERROR");
  });

  it("returns empty errors for XML without error elements", () => {
    const result = parseErrorXml("<result><status><systemStatus>OK</systemStatus></status></result>");
    expect(result.errors).toEqual([]);
  });
});

describe("parseErrorJson", () => {
  it("parses JSON error response", () => {
    const json = JSON.stringify({
      errors: [
        { code: "J001", message: "JSON error", metadata: { propertyPath: "name" } },
      ],
    });
    const result = parseErrorJson(json);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].code).toBe("J001");
    expect(result.errors[0].metadata?.propertyPath).toBe("name");
  });

  it("handles invalid JSON", () => {
    const result = parseErrorJson("{not json}");
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].code).toBe("PARSE_ERROR");
  });
});

describe("extractInlineErrors", () => {
  it("finds inline errors in success HTTP response body", () => {
    const parsed = parseXmlResponse(`<?xml version="1.0" encoding="UTF-8"?>
<result>
  <status>
    <systemStatus>NG</systemStatus>
    <message>Something failed</message>
  </status>
  <errors>
    <error>
      <code>INLINE-001</code>
      <message>Hidden error in 200 response</message>
    </error>
  </errors>
</result>`);

    const errors = extractInlineErrors(parsed);
    expect(errors).toHaveLength(1);
    expect(errors[0].code).toBe("INLINE-001");
  });

  it("creates error from NG status when no explicit errors", () => {
    const parsed = parseXmlResponse(`<?xml version="1.0" encoding="UTF-8"?>
<result>
  <status>
    <systemStatus>NG</systemStatus>
    <message>Generic failure</message>
  </status>
</result>`);

    const errors = extractInlineErrors(parsed);
    expect(errors).toHaveLength(1);
    expect(errors[0].code).toBe("SYSTEM_NG");
    expect(errors[0].message).toBe("Generic failure");
  });

  it("returns empty for clean success response", () => {
    const parsed = parseXmlResponse(`<?xml version="1.0" encoding="UTF-8"?>
<result>
  <status>
    <systemStatus>OK</systemStatus>
  </status>
</result>`);

    expect(extractInlineErrors(parsed)).toEqual([]);
  });

  it("returns empty for non-envelope objects", () => {
    expect(extractInlineErrors({ foo: "bar" })).toEqual([]);
  });
});
