export function normalizeBaseUrl(value: string | undefined) {
  return (value ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
}

export function toWebSocketUrl(baseUrl: string) {
  return baseUrl.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
}

export const env = {
  apiBaseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
  deviceId: import.meta.env.VITE_DEVICE_ID ?? "nexus-demo-esp32",
} as const;
