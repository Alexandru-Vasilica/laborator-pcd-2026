import http from "k6/http";
import { check } from "k6";

// High-concurrency CPU stress: reveals which algorithm handles throttled backends best.
export const options = {
  stages: [
    { duration: "30s", target: 50  },
    { duration: "3m",  target: 100 },
    { duration: "30s", target: 0   },
  ],
  thresholds: {
    http_req_failed:   ["rate<0.01"],
    http_req_duration: ["p(95)<2000"],
  },
};

const baseUrl = __ENV.TARGET || "http://localhost:8080";

export default function () {
  const res = http.get(`${baseUrl}/cpu?duration=0.1`);
  check(res, { "status 200": (r) => r.status === 200 });
}
