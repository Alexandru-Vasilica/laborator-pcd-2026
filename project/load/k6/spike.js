import http from "k6/http";
import { check, sleep } from "k6";

// Sudden spike: tests load-balancer stability under abrupt traffic changes.
export const options = {
  stages: [
    { duration: "10s", target: 5   },
    { duration: "10s", target: 150 },
    { duration: "30s", target: 150 },
    { duration: "10s", target: 5   },
    { duration: "10s", target: 0   },
  ],
  thresholds: {
    http_req_failed:   ["rate<0.05"],
    http_req_duration: ["p(95)<1500"],
  },
};

const baseUrl = __ENV.TARGET || "http://localhost:8080";

export default function () {
  const path = Math.random() < 0.5 ? "/work?ms=50" : "/get";
  const res = http.get(`${baseUrl}${path}`);
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(0.02);
}
