#!/bin/bash
set -euo pipefail

CONTEXT="k3d-dlb"
ENVOY_LOCAL_PORT="${ENVOY_LOCAL_PORT:-18080}"

require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: Missing required tool '$1'."
    echo "Install it from the README prerequisites and re-run."
    exit 1
  fi
}

require_tool kubectl
require_tool k6

if ! kubectl config get-contexts -o name | grep -qx "$CONTEXT"; then
  echo "ERROR: kube context '$CONTEXT' not found. Run 'make setup' first."
  exit 1
fi

if ! kubectl --context "$CONTEXT" get ns >/dev/null 2>&1; then
  echo "ERROR: Unable to reach cluster for context '$CONTEXT'. Is k3d running?"
  exit 1
fi

cleanup() {
  if [[ -n "${ENVOY_PID:-}" ]]; then
    kill "$ENVOY_PID" 2>/dev/null || true
  fi
  if [[ -n "${GRAFANA_PID:-}" ]]; then
    kill "$GRAFANA_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Port forward Envoy in the background
echo "Port-forwarding Envoy to :${ENVOY_LOCAL_PORT}..."
kubectl -n dlb port-forward svc/dlb-envoy "${ENVOY_LOCAL_PORT}:80" --context "$CONTEXT" > /dev/null 2>&1 &
ENVOY_PID=$!

# Port forward Grafana in the background
echo "Port-forwarding Grafana to :3000..."
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80 --context "$CONTEXT" > /dev/null 2>&1 &
GRAFANA_PID=$!

sleep 1
if ! kill -0 "$ENVOY_PID" 2>/dev/null; then
  echo "ERROR: Envoy port-forward failed. Check if port ${ENVOY_LOCAL_PORT} is in use."
  exit 1
fi
if ! kill -0 "$GRAFANA_PID" 2>/dev/null; then
  echo "ERROR: Grafana port-forward failed. Check if port 3000 is in use."
  exit 1
fi

# Get Grafana password
GRAFANA_PASS=$(kubectl -n monitoring get secret monitoring-grafana -o jsonpath="{.data.admin-password}" --context "$CONTEXT" | base64 --decode)

echo "--------------------------------------------------"
echo "Grafana URL: http://localhost:3000/d/envoy-dlb"
echo "Username: admin"
echo "Password: $GRAFANA_PASS"
echo "--------------------------------------------------"

# Run a quick 20-second load test
echo "Running 20s load test..."
TARGET="http://localhost:${ENVOY_LOCAL_PORT}" k6 run --duration 20s load/k6/steady.js

echo "--------------------------------------------------"
echo "Test complete. Keep this terminal open to access Grafana."
echo "Press Ctrl+C to stop port-forwarding."

# Wait for user to stop
wait $ENVOY_PID $GRAFANA_PID
