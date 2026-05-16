#!/usr/bin/env bash
# run_hpa_experiment.sh
# Runs a CPU-heavy load test with HPA enabled and records the replica/CPU timeline.
# Outputs:
#   results/hpa-scaling-timeline.jsonl  — one JSON object per 5 s poll
#   results/k6-hpa-heavy.json           — per-request k6 latency data
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$ROOT/results"
mkdir -p "$RESULTS_DIR"
ENVOY_LOCAL_PORT="${ENVOY_LOCAL_PORT:-18080}"
CONTEXT="k3d-dlb"
NAMESPACE="dlb"
HPA_NAME="dlb-worker"
DURATION="180s"   # 3 min — HPA stabilisation window is 30 s, needs time to react

echo "=== HPA Scaling Experiment ==="

echo "[1/6] Applying HPA"
kubectl apply -f "$ROOT/k8s/60-hpa.yaml" --context "$CONTEXT"
sleep 2

echo "[2/6] Resetting worker to minReplicas (2) for a clean start"
kubectl -n "$NAMESPACE" scale deploy/dlb-worker --replicas=2 --context "$CONTEXT"
kubectl -n "$NAMESPACE" rollout status deploy/dlb-worker --context "$CONTEXT" --timeout=60s

echo "[3/6] Starting port-forward"
kubectl -n "$NAMESPACE" port-forward svc/dlb-envoy "${ENVOY_LOCAL_PORT}:80" \
  --context "$CONTEXT" > /tmp/pf-hpa-envoy.log 2>&1 &
PF_PID=$!
sleep 3

TIMELINE_FILE="$RESULTS_DIR/hpa-scaling-timeline.jsonl"
K6_OUT="$RESULTS_DIR/k6-hpa-heavy.json"
: > "$TIMELINE_FILE"

cleanup() {
  kill "$MONITOR_PID" 2>/dev/null || true
  kill "$K6_PID"      2>/dev/null || true
  kill "$PF_PID"      2>/dev/null || true
}
trap cleanup EXIT

START_TS=$(date +%s)

echo "[4/6] Starting HPA monitor (polls every 5 s)"
(
  while true; do
    TS=$(date +%s)
    ELAPSED=$(( TS - START_TS ))
    REPLICAS=$(kubectl -n "$NAMESPACE" get hpa "$HPA_NAME" \
      --context "$CONTEXT" \
      -o jsonpath='{.status.currentReplicas}' 2>/dev/null || echo "2")
    CPU=$(kubectl -n "$NAMESPACE" get hpa "$HPA_NAME" \
      --context "$CONTEXT" \
      -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}' \
      2>/dev/null || echo "0")
    echo "{\"ts\":$TS,\"elapsed_s\":$ELAPSED,\"replicas\":$REPLICAS,\"cpu_pct\":$CPU}" \
      >> "$TIMELINE_FILE"
    sleep 5
  done
) &
MONITOR_PID=$!

echo "[5/6] Running k6 CPU-heavy load (${DURATION}, 100 VUs)"
TARGET="http://localhost:${ENVOY_LOCAL_PORT}" k6 run \
  --duration "$DURATION" \
  --vus 100 \
  --out "json=$K6_OUT" \
  "$ROOT/load/k6/heavy.js" \
  > "$RESULTS_DIR/log-hpa-heavy.txt" 2>&1 &
K6_PID=$!

wait "$K6_PID" || true

echo "[6/6] Waiting 15 s for final HPA polls after load ends"
sleep 15
kill "$MONITOR_PID" 2>/dev/null || true
kill "$PF_PID"      2>/dev/null || true

echo ""
echo "=== Done ==="
echo "Timeline : $TIMELINE_FILE  ($(wc -l < "$TIMELINE_FILE") samples)"
echo "k6 output: $K6_OUT"
echo "Run 'make results' to regenerate paper figures."
