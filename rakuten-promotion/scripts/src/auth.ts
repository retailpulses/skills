/**
 * Authentication for Rakuten RMS API.
 *
 * Uses the "ESA" (Easy Service Authentication) scheme:
 *   Authorization: ESA <base64(serviceSecret:licenseKey)>
 *
 * Credentials are obtained from the RMS WEB API Service settings panel:
 *   https://mainmenu.rms.rakuten.co.jp/rms
 *
 * The licenseKey expires every 90 days and must be refreshed.
 *
 * Ported from JakeJP/Rakuten.RMS.Api — ServiceProvider.cs
 */

/** Credentials required for Rakuten RMS API authentication. */
export interface RakutenCredentials {
  serviceSecret: string;
  licenseKey: string;
}

/**
 * Build the ESA Authorization header value.
 *
 * Format: "ESA " + Base64(serviceSecret + ":" + licenseKey)
 * Uses ASCII encoding per the reference .NET implementation.
 */
export function buildAuthHeader(credentials: RakutenCredentials): string {
  const raw = `${credentials.serviceSecret}:${credentials.licenseKey}`;
  // btoa expects a binary string; TextEncoder ensures ASCII byte values
  const bytes = new TextEncoder().encode(raw);
  const binary = String.fromCharCode(...bytes);
  const encoded = btoa(binary);
  return `ESA ${encoded}`;
}

/**
 * Read credentials from environment-like object.
 * Checks RAKUTEN_SERVICE_SECRET and RAKUTEN_LICENSE_KEY.
 *
 * @param env — process.env or Workers env binding (record of string|undefined)
 * @returns RakutenCredentials
 * @throws If either credential is missing
 */
export function readCredentials(
  env?: Record<string, string | undefined>,
): RakutenCredentials {
  const serviceSecret = env?.["RAKUTEN_SERVICE_SECRET"];
  const licenseKey = env?.["RAKUTEN_LICENSE_KEY"];

  if (!serviceSecret) {
    throw new Error(
      "Missing RAKUTEN_SERVICE_SECRET. Set it in env vars or .env file.",
    );
  }
  if (!licenseKey) {
    throw new Error(
      "Missing RAKUTEN_LICENSE_KEY. Set it in env vars or .env file. " +
        "Note: license keys expire every 90 days — refresh at RMS WEB API Service settings.",
    );
  }

  return { serviceSecret, licenseKey };
}

/**
 * Mask a credential for safe logging.
 * Shows only the first 4 and last 4 characters.
 */
export function maskCredential(value: string): string {
  if (value.length <= 8) return "****";
  return `${value.slice(0, 4)}****${value.slice(-4)}`;
}
