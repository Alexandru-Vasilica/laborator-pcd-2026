# File-by-File Explanation (Tracked Files)

## Scope and intent
- This document explains each **tracked** file in the repository: what it does, why it exists in the project, and the key inputs/outputs it handles.
- Generated artifacts (for example, build outputs or runtime results) are intentionally excluded so the focus stays on the reproducible, source-controlled artifact.

## How this repo satisfies Project 9 requirements (high level)
- **Baseline and alternatives**: `k8s/43-envoy-config-rr.yaml` defines the round-robin baseline, while `k8s/44-envoy-config-least-request.yaml`, `k8s/45-envoy-config-ring-hash.yaml`, and `k8s/46-envoy-config-maglev.yaml` provide alternative dynamic strategies for comparison.
- **Workload generation and scenarios**: `load/k6/steady.js` and `load/k6/burst.js` define two reproducible workload patterns with explicit thresholds to measure stability, latency, and failure rate.
- **Metrics and observability**: `k8s/50-envoy-servicemonitor.yaml` enables Prometheus scraping, and `grafana/envoy-dashboard.json` defines a dashboard with throughput, latency percentiles, error rate, and availability.
- **Reproducibility and documentation**: `README.md` documents prerequisites, tooling, and execution steps, while `quick-test.sh` provides a deterministic smoke-test flow.

## Root files

### `README.md`
- **What it does**: Serves as the primary documentation: architecture overview, tool versions, prerequisites, quick start, policy switching, experiment scripts, and expected outputs.
- **Why it exists**: The reproducibility requirement demands a clear README with setup instructions, baseline definitions, evaluation scenarios, and artifact descriptions. This file is the “front door” for other teams to reproduce experiments.
- **Key inputs/outputs**:
  - Inputs: required tools (Docker, k3d, kubectl, helm, k6), commands such as `make setup`, `make deploy`, `make test`.
  - Outputs: references to runtime artifacts (e.g., Grafana dashboards) and experiment outputs in `results/` (not tracked).

### `quick-test.sh`
- **What it does**: Runs a 20-second sanity test by port-forwarding Envoy and Grafana, printing Grafana credentials, and executing a k6 load test.
- **Why it exists**: Provides a reproducible smoke test to validate cluster readiness and baseline routing behavior before running longer experiments. This reduces evaluation risk and aligns with the requirement for test scenarios and reproducibility.
- **Key inputs/outputs**:
  - Inputs: kube context `k3d-dlb`, k6 executable, and optional `ENVOY_LOCAL_PORT` environment variable.
  - Outputs: terminal output with Grafana URL/credentials and k6 pass/fail status.

## `grafana/`

### `grafana/envoy-dashboard.json`
- **What it does**: Defines a Grafana dashboard titled “Envoy Load Balancing Overview” with panels for request rate, downstream latency percentiles, error rate, upstream latency percentiles, active connections/requests, and worker availability.
- **Why it exists**: The project requires quantitative metrics, tail-latency tracking, and observability. This dashboard is the visual evaluation tool used during experiments and for evidence in the paper.
- **Key inputs/outputs**:
  - Inputs: Prometheus metrics from Envoy and Kubernetes (Prometheus datasource expected to be named `prometheus`).
  - Outputs: interactive time-series plots used for analysis and reporting.

## `k8s/`

### `k8s/00-namespace.yaml`
- **What it does**: Creates the `dlb` namespace for isolating all DLB resources.
- **Why it exists**: Keeps the testbed clean and reproducible by isolating resources from other Kubernetes workloads.
- **Key inputs/outputs**:
  - Inputs: None beyond `kubectl apply`.
  - Outputs: Namespace `dlb`.

### `k8s/10-worker-deploy.yaml`
- **What it does**: Deploys three standard worker pods using the `dlb-worker:latest` image and exposes HTTP on port 8080.
- **Why it exists**: Provides the worker pool that the load balancer targets, enabling comparison of scheduling policies on a consistent backend.
- **Key inputs/outputs**:
  - Inputs: Container image `dlb-worker:latest`, environment variables `POD_NAME`, `BASE_DELAY_MS=0`, `PORT=8080`.
  - Outputs: Three running pods with readiness and liveness probes on `/health`.

### `k8s/20-worker-svc.yaml`
- **What it does**: Creates a **headless** service (`clusterIP: None`) for `dlb-worker` with ports for HTTP and metrics.
- **Why it exists**: Headless service exposes one A-record per pod so Envoy’s `STRICT_DNS` can load-balance at the pod level, which is essential for meaningful policy comparison.
- **Key inputs/outputs**:
  - Inputs: Selector label `app: dlb-worker`.
  - Outputs: DNS name `dlb-worker.dlb.svc.cluster.local` resolving to individual pod IPs.

### `k8s/41-envoy-deploy.yaml`
- **What it does**: Deploys a single Envoy proxy container using `envoyproxy/envoy:v1.30.1`, mounting its configuration from a ConfigMap.
- **Why it exists**: Envoy is the load balancer under test; the deployment is the core “dynamic load balancing” artifact.
- **Key inputs/outputs**:
  - Inputs: ConfigMap `dlb-envoy-config`, ports `8080` (HTTP) and `9901` (admin).
  - Outputs: Envoy pod exposing the data plane and metrics/admin endpoints.

### `k8s/42-envoy-svc.yaml`
- **What it does**: Exposes the Envoy pod via a ClusterIP service with HTTP and admin ports.
- **Why it exists**: Enables port-forwarding for local testing and metric scraping through the ServiceMonitor.
- **Key inputs/outputs**:
  - Inputs: Selector label `app: dlb-envoy`.
  - Outputs: Service endpoints on port `80` (HTTP) and `9901` (admin).

### `k8s/43-envoy-config-rr.yaml`
- **What it does**: Envoy ConfigMap with `lb_policy: ROUND_ROBIN`.
- **Why it exists**: Defines the baseline scheduling policy required by the project rubric.
- **Key inputs/outputs**:
  - Inputs: DNS target `dlb-worker.dlb.svc.cluster.local`, listener on `0.0.0.0:8080`.
  - Outputs: Round-robin routing decisions for comparison.

### `k8s/44-envoy-config-least-request.yaml`
- **What it does**: Envoy ConfigMap with `lb_policy: LEAST_REQUEST`.
- **Why it exists**: Represents a dynamic policy that should outperform round-robin when workers have uneven latency or load.
- **Key inputs/outputs**:
  - Inputs: Same listener/cluster wiring as the baseline.
  - Outputs: Load balancing decisions based on in-flight requests.

### `k8s/45-envoy-config-ring-hash.yaml`
- **What it does**: Envoy ConfigMap with `lb_policy: RING_HASH`.
- **Why it exists**: Implements consistent hashing to test stability and distribution under topology changes.
- **Key inputs/outputs**:
  - Inputs: Same listener/cluster wiring as the baseline.
  - Outputs: Hash-based routing behavior for evaluation.

### `k8s/46-envoy-config-maglev.yaml`
- **What it does**: Envoy ConfigMap with `lb_policy: MAGLEV`.
- **Why it exists**: Provides a modern consistent-hash algorithm (Maglev) to compare with ring hash and least-request.
- **Key inputs/outputs**:
  - Inputs: Same listener/cluster wiring as the baseline.
  - Outputs: Maglev routing decisions with reduced churn.

### `k8s/50-envoy-servicemonitor.yaml`
- **What it does**: Prometheus ServiceMonitor that scrapes Envoy’s `/stats/prometheus` endpoint every 15 seconds.
- **Why it exists**: Supplies quantitative metrics (throughput, latency, errors) necessary for evaluation and reporting.
- **Key inputs/outputs**:
  - Inputs: Service selector `app: dlb-envoy`, port `admin`.
  - Outputs: Prometheus time-series for Envoy metrics.

## `load/k6/`

### `load/k6/steady.js`
- **What it does**: k6 script that ramps to a steady workload (20 → 50 → 20 VUs) with a 20% slow-request ratio.
- **Why it exists**: Provides a stable workload scenario to compare policies under controlled, steady traffic.
- **Key inputs/outputs**:
  - Inputs: `TARGET` base URL, `SLOW_RATIO`, endpoints `/work?ms=5` and `/work?ms=500`.
  - Outputs: k6 metrics including thresholds (`p95 < 1500ms`, failure rate < 1%).

### `load/k6/burst.js`
- **What it does**: k6 script for bursty traffic (10 → 60 → 10 → 80 → 10 VUs) with a 30% slow-request ratio.
- **Why it exists**: Exercises stability and recovery under sudden changes in load, aligning with the failure/stress scenario requirement.
- **Key inputs/outputs**:
  - Inputs: `TARGET` base URL, `SLOW_RATIO`, endpoints `/work?ms=5` and `/work?ms=500`.
  - Outputs: k6 metrics with the same tail-latency and failure thresholds for consistent comparison.
