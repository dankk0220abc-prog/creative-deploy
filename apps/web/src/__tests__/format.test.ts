import { describe, expect, it } from "vitest";

import {
  formatProjectAccessibleTimestamp,
  formatProjectRelativeTime,
  formatProjectTimestamp,
} from "../utils/format";

const NOW = new Date("2026-07-28T12:00:00.000Z").getTime();

describe("project time formatting", () => {
  it.each([
    ["2026-07-28T11:59:31.000Z", "just now"],
    ["2026-07-28T11:55:00.000Z", "5 minutes ago"],
    ["2026-07-28T09:00:00.000Z", "3 hours ago"],
    ["2026-07-25T12:00:00.000Z", "3 days ago"],
    ["2026-07-28T12:05:00.000Z", "in 5 minutes"],
    ["not-a-time", "Unknown update time"],
  ])("formats %s relative to an injected now", (value, expected) => {
    expect(formatProjectRelativeTime(value, NOW)).toBe(expected);
  });

  it("formats an exact accessible timestamp without relying on the runtime locale", () => {
    expect(formatProjectAccessibleTimestamp("2026-07-27T10:00:00.000Z")).toBe(
      "July 27, 2026 at 10:00:00 AM UTC",
    );
    expect(formatProjectAccessibleTimestamp("not-a-time")).toBe(
      "Unknown update time",
    );
    expect(formatProjectTimestamp("not-a-time")).toBe("Unknown update time");
  });
});
