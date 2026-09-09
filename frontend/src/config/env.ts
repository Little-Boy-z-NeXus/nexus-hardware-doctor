export function normalizeBaseUrl(value: string | undefined) {
  return (value ?? "http://localhost:8000").replace(/\/+$/, "");
}

export const env = {
  apiBaseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
  deviceId: import.meta.env.VITE_DEVICE_ID ?? "nexus-demo-esp32",
} as const;
