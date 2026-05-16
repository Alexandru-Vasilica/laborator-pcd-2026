#!/usr/bin/env bash
# fault_injection.sh <policy>
# Deletes all worker pods during an active load test and measures recovery time.
set -euo pipefail

POLICY="${1:?Usage: $0 <policy>}"

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
  echo "ERROR: Unknown policy '$POLICY'." >&2
  exit 1
fi

echo "=== Fault Injection: policy=$POLICY ==="

echo "[1/6] Applying Envoy config and restarting"
kubectl apply -f "$ROOT/$CONFIG_FILE" --context k3d-dlb
kubectl rollout restart deploy/dlb-envoy -n dlb --context k3d-dlb
kubectl rollout status  deploy/dlb-envoy -n dlb --context k3d-dlb --timeout=60s

echo "[2/6] Starting port-forward"
kubectl -n dlb port-forward svc/dlb-envoy "${ENVOY_LOCAL_PORT}:80" --context k3d-dlb > /tmp/pf-fault-envoy.log 2>&1 &
PF_ENVOY=$!
sleep 3

cleanup() {
  kill "$PF_ENVOY" 2>/dev/null || true
  kill "$K6_PID"   2>/dev/null || true
}
trap cleanup EXIT

K6_OUT="$RESULTS_DIR/k6-fault-${POLICY}.json"

echo "[3/6] Starting k6 steady load in background (60s)"
TARGET="http://localhost:${ENVOY_LOCAL_PORT}" k6 run \
  --duration 60s \
  --vus 20 \
  --out "json=$K6_OUT" \
  "$ROOT/load/k6/steady.js" \
  > "$RESULTS_DIR/log-fault-${POLICY}.txt" 2>&1 &
K6_PID=$!

echo "[4/6] Waiting 20s before injecting fault"
sleep 20

echo "[5/6] Injecting fault: deleting all dlb-worker pods"
DELETION_TS=$(date +%s)
kubectl -n dlb delete pod -l app=dlb-worker --wait=false --context k3d-dlb
echo "Pods deleted at timestamp: $DELETION_TS"

echo "[6/6] Waiting for all pods to become Ready again"
RECOVERY_START=$(date +%s)
TIMEOUT=120
while true; do
  READY=$(kubectl -n dlb get pods -l app=dlb-worker \
    --context k3d-dlb \
    -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null \
    | tr ' ' '\n' | grep -c "true" || true)
  TOTAL=$(kubectl -n dlb get pods -l app=dlb-worker \
    --context k3d-dlb \
    --no-headers 2>/dev/null | wc -l || true)
  if [[ "$TOTAL" -ge 4 && "$READY" -ge 4 ]]; then
    break
  fi
  NOW=$(date +%s)
  if (( NOW - RECOVERY_START > TIMEOUT )); then
    echo "WARNING: Pods did not recover within ${TIMEOUT}s" >&2
    break
  fi
  sleep 2
done
RECOVERY_END=$(date +%s)
RECOVERY_TIME=$(( RECOVERY_END - DELETION_TS ))

echo "Recovery time: ${RECOVERY_TIME}s"

# Wait for k6 to finish
wait "$K6_PID" || true

# Write result JSON
RESULT_FILE="$RESULTS_DIR/fault-${POLICY}.json"
cat > "$RESULT_FILE" <<EOF
{
  "policy": "$POLICY",
  "deletion_ts": $DELETION_TS,
  "recovery_time_s": $RECOVERY_TIME,
  "k6_output": "$K6_OUT"
}
EOF

echo "=== Fault injection result saved to $RESULT_FILE ==="
