import { describe, expect, it } from "vitest";

import { normalizeBaseUrl } from "./env";

describe("normalizeBaseUrl", () => {
  it("uses the local backend when no override is provided", () => {
    expect(normalizeBaseUrl(undefined)).toBe("http://localhost:8000");
  });

  it("removes trailing slashes before endpoint paths are appended", () => {
    expect(normalizeBaseUrl("https://api.nexus.example///")).toBe(
      "https://api.nexus.example",
    );
  });

  it("preserves a configured base path", () => {
    expect(normalizeBaseUrl("https://api.nexus.example/v1")).toBe(
      "https://api.nexus.example/v1",
    );
  });
});
