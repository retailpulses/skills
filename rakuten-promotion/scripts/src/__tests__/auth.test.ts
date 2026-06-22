/**
 * Tests for authentication utilities.
 */
import { describe, it, expect } from "vitest";
import { buildAuthHeader, readCredentials, maskCredential } from "../auth.js";

describe("buildAuthHeader", () => {
  it("builds ESA header from serviceSecret and licenseKey", () => {
    const header = buildAuthHeader({
      serviceSecret: "test-secret",
      licenseKey: "test-license",
    });
    expect(header).toMatch(/^ESA /);
    // Decode and verify
    const encoded = header.slice(4); // remove "ESA "
    const decoded = atob(encoded);
    expect(decoded).toBe("test-secret:test-license");
  });

  it("works with special characters in secret", () => {
    const header = buildAuthHeader({
      serviceSecret: "s3cr3t!@#",
      licenseKey: "key-with-dashes",
    });
    expect(header).toMatch(/^ESA /);
    const decoded = atob(header.slice(4));
    expect(decoded).toBe("s3cr3t!@#:key-with-dashes");
  });

  it("produces consistent output", () => {
    const a = buildAuthHeader({ serviceSecret: "a", licenseKey: "b" });
    const b = buildAuthHeader({ serviceSecret: "a", licenseKey: "b" });
    expect(a).toBe(b);
  });
});

describe("readCredentials", () => {
  it("reads from env object", () => {
    const creds = readCredentials({
      RAKUTEN_SERVICE_SECRET: "ss",
      RAKUTEN_LICENSE_KEY: "lk",
    });
    expect(creds).toEqual({ serviceSecret: "ss", licenseKey: "lk" });
  });

  it("throws if serviceSecret is missing", () => {
    expect(() =>
      readCredentials({ RAKUTEN_LICENSE_KEY: "lk" }),
    ).toThrow("Missing RAKUTEN_SERVICE_SECRET");
  });

  it("throws if licenseKey is missing", () => {
    expect(() =>
      readCredentials({ RAKUTEN_SERVICE_SECRET: "ss" }),
    ).toThrow("Missing RAKUTEN_LICENSE_KEY");
  });

  it("throws if both are missing", () => {
    expect(() => readCredentials({})).toThrow();
  });

  it("works with undefined env (uses error message)", () => {
    expect(() => readCredentials(undefined)).toThrow("Missing RAKUTEN_SERVICE_SECRET");
  });
});

describe("maskCredential", () => {
  it("shows first 4 and last 4 chars", () => {
    expect(maskCredential("abcdefghijklmnop")).toBe("abcd****mnop");
  });

  it("returns **** for short values", () => {
    expect(maskCredential("short")).toBe("****");
  });

  it("handles exactly 8 chars", () => {
    expect(maskCredential("12345678")).toBe("****");
  });
});
