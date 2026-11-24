import { describe, expect, it } from "vitest";

import { isValidMobile, MOBILE_MAX_LENGTH } from "./validation";

describe("mobile numbers", () => {
  it.each(["+919876543210", "+91 98765-43210", "+12345678", "+123456789012345"])(
    "accepts %s",
    (mobile) => {
      expect(isValidMobile(mobile)).toBe(true);
    },
  );

  it("accepts exactly 20 characters as typed", () => {
    const mobile = "+1 2 3 4 5 6 7 8 9 0";

    expect(mobile).toHaveLength(MOBILE_MAX_LENGTH);
    expect(isValidMobile(mobile)).toBe(true);
  });

  // Valid once the spaces go, but longer than the server's 20-character limit on raw input.
  it("refuses more than 20 characters as typed", () => {
    const mobile = "+91 9 8 7 6 5 4 3 2 1 0";

    expect(mobile.length).toBeGreaterThan(MOBILE_MAX_LENGTH);
    expect(isValidMobile(mobile.replaceAll(" ", ""))).toBe(true);
    expect(isValidMobile(mobile)).toBe(false);
  });

  it.each(["09876543210", "+0123456789", "+1234567", "+1234567890123456", "+91 abc", "+", ""])(
    "refuses %j",
    (mobile) => {
      expect(isValidMobile(mobile)).toBe(false);
    },
  );
});
