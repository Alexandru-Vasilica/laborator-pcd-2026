import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "20s", target: 10 },
    { duration: "20s", target: 60 },
    { duration: "20s", target: 10 },
    { duration: "20s", target: 80 },
    { duration: "20s", target: 10 },
  ],
  thresholds: {
    http_req_failed:   ["rate<0.01"],
    http_req_duration: ["p(95)<1500"],
  },
};

const baseUrl   = __ENV.TARGET     || "http://localhost:8080";
const slowRatio = Number(__ENV.SLOW_RATIO || 0.3);

export default function () {
  const path = Math.random() < slowRatio ? "/work?ms=500" : "/work?ms=5";
  const res = http.get(`${baseUrl}${path}`);
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(0.05);
}
