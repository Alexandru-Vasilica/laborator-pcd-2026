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
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

const baseUrl = __ENV.TARGET || "http://localhost:8080";
const slowRatio = Number(__ENV.SLOW_RATIO || 0.3);

export default function () {
  const useSlow = Math.random() < slowRatio;
  const path = useSlow ? "/delay/1" : "/get";
  const res = http.get(`${baseUrl}${path}`);
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(0.05);
}
