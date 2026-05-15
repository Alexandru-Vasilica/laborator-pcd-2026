# Distributed Load Balancer (DLB) - Envoy & K3s

This project demonstrates various load balancing policies using Envoy proxy in a Kubernetes (k3s) environment. It includes a worker service, metrics collection with Prometheus/Grafana, and load testing scripts.

## Prerequisites

- [Docker](https://www.docker.com/)
- [k3d](https://k3d.io/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [helm](https://helm.sh/)
- [k6](https://k6.io/)

## Setup

### 1. Create the Cluster

```bash
k3d cluster create dlb \
  --servers 1 \
  --agents 2 \
  --port "8080:80@loadbalancer" \
  --k3s-arg "--disable=traefik@server:*"
```

### 2. Deploy the Worker Service

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/10-worker-deploy.yaml
kubectl apply -f k8s/20-worker-svc.yaml
```

### 3. Deploy Envoy Proxy

By default, this applies the Round Robin policy.

```bash
kubectl apply -f k8s/43-envoy-config-rr.yaml
kubectl apply -f k8s/41-envoy-deploy.yaml
kubectl apply -f k8s/42-envoy-svc.yaml
```

## Load Balancing Policies

You can switch between different load balancing policies by applying the corresponding ConfigMap and restarting Envoy.

### Round Robin (Default)
```bash
kubectl apply -f k8s/43-envoy-config-rr.yaml
kubectl rollout restart deploy/dlb-envoy -n dlb
```

### Least Request
```bash
kubectl apply -f k8s/44-envoy-config-least-request.yaml
kubectl rollout restart deploy/dlb-envoy -n dlb
```

### Ring Hash
```bash
kubectl apply -f k8s/45-envoy-config-ring-hash.yaml
kubectl rollout restart deploy/dlb-envoy -n dlb
```

### Maglev
```bash
kubectl apply -f k8s/46-envoy-config-maglev.yaml
kubectl rollout restart deploy/dlb-envoy -n dlb
```

## Metrics & Monitoring

Metrics are collected using Prometheus and visualized in Grafana.

### 1. Install Prometheus Stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace
```

### 2. Enable Envoy Metrics Scraping

```bash
kubectl apply -f k8s/50-envoy-servicemonitor.yaml
```

### 3. Access Grafana

Port-forward to the Grafana service:
```bash
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
```

Get the `admin` password:
```bash
kubectl -n monitoring get secret monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 --decode
```

### 4. Import Dashboard

Import the dashboard located at `grafana/envoy-dashboard.json` into Grafana.

## Load Testing

Use [k6](https://k6.io/) to run load tests against the Envoy proxy.

```bash
# Steady load
TARGET=http://localhost:8080 k6 run load/k6/steady.js

# Bursty load
TARGET=http://localhost:8080 k6 run load/k6/burst.js
```

## Experiments

To evaluate the policies:
1. Apply a policy.
2. Run a workload (steady or burst).
3. Inject a failure (e.g., `kubectl -n dlb delete pod -l app=dlb-worker`).
4. Observe metrics in Grafana (latency, throughput, error rate).
