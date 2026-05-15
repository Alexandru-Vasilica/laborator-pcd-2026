#!/bin/bash

# Ensure we are using the correct context
kubectl config use-context k3d-dlb

# Port forward Envoy in the background
echo "Port-forwarding Envoy to :8080..."
kubectl -n dlb port-forward svc/dlb-envoy 8080:80 > /dev/null 2>&1 &
ENVOY_PID=$!

# Port forward Grafana in the background
echo "Port-forwarding Grafana to :3000..."
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80 > /dev/null 2>&1 &
GRAFANA_PID=$!

# Get Grafana password
GRAFANA_PASS=$(kubectl -n monitoring get secret monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 --decode)

echo "--------------------------------------------------"
echo "Grafana URL: http://localhost:3000/d/envoy-dlb"
echo "Username: admin"
echo "Password: $GRAFANA_PASS"
echo "--------------------------------------------------"

# Run a quick 20-second load test
echo "Running 20s load test..."
TARGET=http://localhost:8080 k6 run --duration 20s load/k6/steady.js

echo "--------------------------------------------------"
echo "Test complete. Keep this terminal open to access Grafana."
echo "Press Ctrl+C to stop port-forwarding."

# Wait for user to stop
wait $ENVOY_PID $GRAFANA_PID
