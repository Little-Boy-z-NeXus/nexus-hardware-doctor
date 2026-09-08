import http from "k6/http";
import { check, group } from "k6";

const apiBaseUrl = (__ENV.NEXUS_API_BASE_URL || "http://127.0.0.1:8000").replace(
  /\/+$/,
  "",
);
const webBaseUrl = (__ENV.NEXUS_WEB_BASE_URL || "http://127.0.0.1:5173").replace(
  /\/+$/,
  "",
);

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
