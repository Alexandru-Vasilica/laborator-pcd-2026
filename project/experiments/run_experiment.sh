#!/usr/bin/env bash
# run_experiment.sh <policy> <scenario>
# policy: rr | least-request | ring-hash | maglev
# scenario: steady | burst | heavy | spike
set -euo pipefail

POLICY="${1:?Usage: $0 <policy> <scenario>}"
SCENARIO="${2:?Usage: $0 <policy> <scenario>}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$ROOT/results"
mkdir -p "$RESULTS_DIR"
ENVOY_LOCAL_PORT="${ENVOY_LOCAL_PORT:-18080}"

declare -A POLICY_FILE=(
  [rr]="k8s/43-envoy-config-rr.yaml"
  [least-request]="k8s/44-envoy-config-least-request.yaml"
  [ring-hash]="k8s/45-envoy-config-ring-hash.yaml"
  [maglev]="k8s/46-envoy-config-maglev.yaml"
)

CONFIG_FILE="${POLICY_FILE[$POLICY]:-}"
if [[ -z "$CONFIG_FILE" ]]; then
  echo "ERROR: Unknown policy '$POLICY'. Choose: rr | least-request | ring-hash | maglev" >&2
  exit 1
fi

echo "=== Experiment: policy=$POLICY  scenario=$SCENARIO ==="

echo "[1/5] Applying Envoy config: $CONFIG_FILE"
kubectl apply -f "$ROOT/$CONFIG_FILE" --context k3d-dlb

echo "[2/5] Restarting Envoy and waiting for rollout"
kubectl rollout restart deploy/dlb-envoy -n dlb --context k3d-dlb
kubectl rollout status  deploy/dlb-envoy -n dlb --context k3d-dlb --timeout=60s

echo "[3/5] Starting port-forwards"
kubectl -n dlb        port-forward svc/dlb-envoy              "${ENVOY_LOCAL_PORT}:80"   --context k3d-dlb > /tmp/pf-envoy.log    2>&1 &
PF_ENVOY=$!
kubectl -n monitoring port-forward svc/monitoring-prometheus-prometheus 9090:9090 --context k3d-dlb > /tmp/pf-prom.log 2>&1 &
PF_PROM=$!
sleep 3  # allow port-forwards to establish

cleanup() {
  kill "$PF_ENVOY" "$PF_PROM" 2>/dev/null || true
}
trap cleanup EXIT

echo "[4/5] Running k6 scenario: $SCENARIO"
K6_OUT="$RESULTS_DIR/k6-${POLICY}-${SCENARIO}.json"
TARGET="http://localhost:${ENVOY_LOCAL_PORT}" k6 run \
  --out "json=$K6_OUT" \
  "$ROOT/load/k6/${SCENARIO}.js" \
  2>&1 | tee "$RESULTS_DIR/log-${POLICY}-${SCENARIO}.txt"

echo "[5/5] Collecting Prometheus metrics"
"$ROOT/experiments/collect_prometheus.sh" "$POLICY" "$SCENARIO"

echo "=== Done: results saved to $RESULTS_DIR ==="
