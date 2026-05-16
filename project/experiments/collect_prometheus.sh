#!/usr/bin/env bash
# collect_prometheus.sh <policy> <scenario>
# Queries the Prometheus HTTP API and saves key metrics to results/.
set -euo pipefail

POLICY="${1:?Usage: $0 <policy> <scenario>}"
SCENARIO="${2:?Usage: $0 <policy> <scenario>}"

PROM_URL="${PROM_URL:-http://localhost:9090}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$ROOT/results"
mkdir -p "$RESULTS_DIR"

query() {
  local q="$1"
  curl -sf "${PROM_URL}/api/v1/query" --data-urlencode "query=${q}" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    print(results[0]['value'][1])
else:
    print('null')
" 2>/dev/null || echo "null"
}

echo "Collecting Prometheus metrics for policy=$POLICY scenario=$SCENARIO"

# Envoy downstream latency (milliseconds histogram)
P50=$(query  "histogram_quantile(0.50, sum(rate(envoy_http_downstream_rq_time_bucket{envoy_http_conn_manager_prefix=\"ingress_http\"}[2m])) by (le))")
P95=$(query  "histogram_quantile(0.95, sum(rate(envoy_http_downstream_rq_time_bucket{envoy_http_conn_manager_prefix=\"ingress_http\"}[2m])) by (le))")
P99=$(query  "histogram_quantile(0.99, sum(rate(envoy_http_downstream_rq_time_bucket{envoy_http_conn_manager_prefix=\"ingress_http\"}[2m])) by (le))")

# Throughput (req/s)
THROUGHPUT=$(query "sum(rate(envoy_http_downstream_rq_total{envoy_http_conn_manager_prefix=\"ingress_http\"}[2m]))")

# Error rate (5xx / total)
ERRORS_5XX=$(query "sum(rate(envoy_http_downstream_rq_xx{envoy_http_conn_manager_prefix=\"ingress_http\",envoy_response_code_class=\"5\"}[2m]))")

# Per-pod active connections (worker metrics)
ACTIVE_REQS=$(query "sum by (pod) (worker_active_requests)" 2>/dev/null || echo "null")

OUT="$RESULTS_DIR/prom-${POLICY}-${SCENARIO}.json"
cat > "$OUT" <<EOF
{
  "policy": "$POLICY",
  "scenario": "$SCENARIO",
  "latency_ms": {
    "p50": $P50,
    "p95": $P95,
    "p99": $P99
  },
  "throughput_rps": $THROUGHPUT,
  "errors_5xx_rps": $ERRORS_5XX
}
EOF

echo "Prometheus metrics saved to $OUT"
echo "  p50=${P50}ms  p95=${P95}ms  p99=${P99}ms  rps=${THROUGHPUT}  5xx=${ERRORS_5XX}"
