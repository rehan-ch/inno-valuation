import { describe, expect, it } from "vitest";

import { safeNextPath, signInHref } from "./next-param";

const ORIGIN = "https://app.example.com";

describe("safeNextPath", () => {
  it("returns the resolved path and query of a same-site path", () => {
    expect(safeNextPath("/team?x=1", ORIGIN)).toBe("/team?x=1");
    expect(safeNextPath("/invitations/accept", ORIGIN)).toBe("/invitations/accept");
  });

  it("drops a hash, which the caller carries separately", () => {
    expect(safeNextPath("/team#x", ORIGIN)).toBe("/team");
  });

  it.each([
    ["a tab", "/\t/evil.com"],
    ["a newline", "/\n/evil.com"],
    ["a carriage return", "/\r/evil.com"],
    ["a scheme-relative URL", "//evil.com"],
    ["a backslash path", "/\\evil.com"],
    ["an absolute URL", "https://evil.com"],
    ["a relative path", "team"],
    ["an empty value", ""],
    ["no value", null],
  ])("rejects %s", (_name, raw) => {
    expect(safeNextPath(raw, ORIGIN)).toBeNull();
  });
});

describe("signInHref", () => {
  it("carries the current path, query and hash", () => {
    window.history.replaceState(null, "", "/team?x=1#token=abc");
    expect(signInHref()).toBe("/sign-in?next=%2Fteam%3Fx%3D1#token=abc");
  });
});
