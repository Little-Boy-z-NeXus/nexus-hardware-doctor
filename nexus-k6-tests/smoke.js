import http from "k6/http";
import { check, group } from "k6";
import ws from "k6/ws";

const apiBaseUrl = (__ENV.NEXUS_API_BASE_URL || "http://127.0.0.1:8000").replace(
  /\/+$/,
  "",
);
const webBaseUrl = (__ENV.NEXUS_WEB_BASE_URL || "http://127.0.0.1:5173").replace(
  /\/+$/,
  "",
);
const wsBaseUrl = apiBaseUrl.replace(/^http:/, "ws:").replace(/^https:/, "wss:");

export const options = {
  scenarios: {
    smoke: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 1,
      maxDuration: "30s",
      gracefulStop: "0s",
    },
  },
  thresholds: {
    checks: ["rate==1"],
    http_req_failed: ["rate==0"],
    "http_req_duration{target:api-health}": ["p(95)<500"],
    "http_req_duration{target:api-live}": ["p(95)<500"],
    "http_req_duration{target:frontend}": ["p(95)<1000"],
  },
};

export default function () {
  group("backend health contract", () => {
    const response = http.get(`${apiBaseUrl}/health`, {
      tags: { target: "api-health" },
    });
    let payload = {};

    try {
      payload = response.json();
    } catch (_) {
      // The check below reports a readable contract failure for non-JSON responses.
    }

    check(response, {
      "backend returns HTTP 200": (result) => result.status === 200,
      "backend identifies the nexus service": () => payload.service === "nexus-backend",
      "backend reports healthy": () => payload.status === "ok",
    });
  });

  group("realtime hardware snapshot", () => {
    const response = http.get(`${apiBaseUrl}/api/v1/live`, {
      tags: { target: "api-live" },
    });
    let payload = {};
    try {
      payload = response.json();
    } catch (_) {
      // The checks below identify a malformed API payload.
    }

    check(response, {
      "live snapshot returns HTTP 200": (result) => result.status === 200,
      "snapshot contains connection state": () => typeof payload.connection?.status === "string",
      "snapshot is pinned to MVP hardware": () =>
        payload.hardware?.hardware_model_id === "nexus-s3-ina226-l298n-motor-rig-v1",
    });

    let receivedSnapshot = false;
    const upgrade = ws.connect(`${wsBaseUrl}/api/v1/live/ws`, {}, (socket) => {
      socket.on("message", (rawMessage) => {
        try {
          const message = JSON.parse(rawMessage);
          receivedSnapshot = message.type === "snapshot" && Boolean(message.data?.hardware);
        } catch (_) {
          receivedSnapshot = false;
        }
        socket.close();
      });
      socket.setTimeout(() => socket.close(), 3000);
    });

    check(upgrade, {
      "WebSocket upgrades successfully": (result) => result?.status === 101,
      "WebSocket sends initial snapshot": () => receivedSnapshot,
    });
  });

  group("frontend route fallback", () => {
    for (const route of ["/dashboard", "/hardware", "/doctor"]) {
      const response = http.get(`${webBaseUrl}${route}`, {
        tags: { target: "frontend", route },
      });

      check(response, {
        [`${route} returns HTTP 200`]: (result) => result.status === 200,
        [`${route} serves the React root`]: (result) =>
          typeof result.body === "string" && result.body.includes('id="root"'),
      });
    }
  });
}
