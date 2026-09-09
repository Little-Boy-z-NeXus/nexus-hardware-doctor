import http from "k6/http";
import { check, sleep } from "k6";

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
    mvp_baseline: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "5s", target: 3 },
        { duration: "15s", target: 5 },
        { duration: "5s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    http_req_failed: ["rate<0.01"],
    "http_req_duration{target:api-health}": ["p(95)<300"],
    "http_req_duration{target:frontend}": ["p(95)<750"],
  },
};

export default function () {
  const health = http.get(`${apiBaseUrl}/health`, {
    tags: { target: "api-health" },
  });
  check(health, {
    "health remains available": (response) => response.status === 200,
  });

  const dashboard = http.get(`${webBaseUrl}/dashboard`, {
    tags: { target: "frontend" },
  });
  check(dashboard, {
    "dashboard remains available": (response) => response.status === 200,
  });

  sleep(1);
}
