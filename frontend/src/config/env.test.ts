import { describe, expect, it } from "vitest";

import { normalizeBaseUrl, toWebSocketUrl } from "./env";

describe("normalizeBaseUrl", () => {
  it("uses the local backend when no override is provided", () => {
    expect(normalizeBaseUrl(undefined)).toBe("http://127.0.0.1:8000");
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

describe("toWebSocketUrl", () => {
  it("maps local HTTP and hosted HTTPS API URLs to WebSocket protocols", () => {
    expect(toWebSocketUrl("http://localhost:8000")).toBe("ws://localhost:8000");
    expect(toWebSocketUrl("https://api.nexus.example")).toBe("wss://api.nexus.example");
  });
});
