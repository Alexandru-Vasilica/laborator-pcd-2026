# DLB — Dynamic Load Balancing Testbed

A reproducible Kubernetes testbed for comparing Envoy load-balancing policies (Round Robin, Least Request, Ring Hash, Maglev) under steady, bursty, CPU-intensive, and failure-injection workloads.

## Architecture

```
                 ┌──────────────────────────────────────────┐
                 │          k3d / k3s cluster               │
                 │                                          │
   k6 ──────────►│  Envoy proxy                             │
  (load         │  (LB policy: RR | LeastReq | Hash | Maglev)│
   generator)   │       │                                   │
                │  ┌────┴──────────────────────────┐        │
                │  │  dlb-worker headless service  │        │
                │  └──┬──────┬──────┬──────────┬───┘        │
                │  pod-0  pod-1  pod-2    pod-slow           │
                │  (250m CPU)        (50m CPU,               │
                │                    +300ms delay)           │
                │                                          │
                │  Prometheus ◄── /stats/prometheus (Envoy) │
                │             ◄── /metrics          (pods)  │
                │  Grafana    ◄── Prometheus                 │
                └──────────────────────────────────────────┘
```

The **headless** worker Service (`clusterIP: None`) causes Envoy's `STRICT_DNS` resolver to receive one A-record per pod IP, so each LB policy actually governs per-pod routing. With a normal ClusterIP service all policies would behave identically.

The slow worker (`dlb-worker-slow`) has `BASE_DELAY_MS=300` and a 50 m CPU limit, creating a realistic heterogeneous backend where Least Request measurably outperforms Round Robin.

## Tool Versions (reproducibility)

| Tool      | Version used |
|-----------|-------------|
| k3d       | v5.6.x      |
| k3s/k8s   | v1.28.x     |
| Envoy     | v1.30.1     |
| k6        | v0.51.x     |
| Rust      | 1.78        |
| Helm      | v3.x        |
| kube-prometheus-stack | 58.x |

## Prerequisites

- Docker
- [k3d](https://k3d.io/) (`brew install k3d` / `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash`)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [helm](https://helm.sh/)
- [k6](https://k6.io/) (`brew install k6` / `sudo apt install k6`)
- Python 3.10+ (for analysis scripts)

## Quick Start

```bash
# 1. Create cluster and install Prometheus/Grafana (~3 min)
make setup

# 2. Build the worker image and deploy everything
make deploy

# 3. Sanity check (20-second load test + Grafana link)
make test
```

`make deploy` builds the custom Go worker, imports it into k3d, and applies all manifests in the correct order.

## Repository Layout

```
.
├── worker/                   # Custom Rust HTTP worker (source + Dockerfile)
│   ├── src/main.rs
│   ├── Cargo.toml / Cargo.lock
│   └── Dockerfile
├── k8s/
│   ├── 00-namespace.yaml
│   ├── 10-worker-deploy.yaml       # 3 normal workers (CPU 250m)
│   ├── 11-worker-slow-deploy.yaml  # 1 slow worker (CPU 50m, +300ms delay)
│   ├── 20-worker-svc.yaml          # Headless service (clusterIP: None)
│   ├── 41-envoy-deploy.yaml
│   ├── 42-envoy-svc.yaml
│   ├── 43-envoy-config-rr.yaml         # Round Robin
│   ├── 44-envoy-config-least-request.yaml
│   ├── 45-envoy-config-ring-hash.yaml
│   ├── 46-envoy-config-maglev.yaml
│   ├── 50-envoy-servicemonitor.yaml
│   ├── 51-worker-servicemonitor.yaml
│   ├── 60-hpa.yaml                 # HPA (optional extension)
│   └── 61-prometheus-rules.yaml    # Recording rules
├── load/k6/
│   ├── steady.js   # Ramp 20→50→20 VUs, 20% slow requests
│   ├── burst.js    # Alternating 10↔80 VUs, 30% slow requests
│   ├── heavy.js    # 100 VUs CPU-intensive (/cpu?duration=0.1)
│   └── spike.js    # 0→150→0 VUs sudden spike
├── experiments/
│   ├── run_experiment.sh    # Single policy × scenario run
│   ├── run_all.sh           # All 4 policies × 4 scenarios + fault injection
│   ├── fault_injection.sh   # Pod kill + recovery measurement
│   └── collect_prometheus.sh
├── analysis/
│   ├── requirements.txt
│   ├── plot_results.py      # Generates 5 comparison figures
│   └── summary_table.py     # Generates Markdown + LaTeX tables
├── grafana/
│   ├── envoy-dashboard.json   # Envoy aggregate metrics (6 panels)
│   └── worker-dashboard.json  # Per-pod metrics (5 panels)
├── results/                 # Created at runtime; gitignored
├── Makefile
└── README.md
```

## Load Balancing Policies

Switch policies by applying the matching ConfigMap and restarting Envoy:

```bash
kubectl apply -f k8s/44-envoy-config-least-request.yaml
kubectl rollout restart deploy/dlb-envoy -n dlb
kubectl rollout status  deploy/dlb-envoy -n dlb
```

| Policy | Config file | Key behaviour |
|--------|-------------|---------------|
| Round Robin | `43-envoy-config-rr.yaml` | Cycles through pods equally — baseline |
| Least Request | `44-envoy-config-least-request.yaml` | Sends to pod with fewest active requests |
| Ring Hash | `45-envoy-config-ring-hash.yaml` | Consistent hashing by client IP |
| Maglev | `46-envoy-config-maglev.yaml` | Google's consistent hash — minimal disruption on topology change |

## Worker Endpoints

The custom Rust worker (`worker/src/main.rs`, built with axum + tokio) exposes:

| Endpoint | Description |
|----------|-------------|
| `GET /` or `/get` | Fast response; returns `{"pod":"...","ts":...}` + `X-Pod-Name` header |
| `GET /work?ms=N` | Sleeps N ms (+ `BASE_DELAY_MS`) then responds |
| `GET /cpu?duration=N` | Burns CPU for N seconds (busy-loop) |
| `GET /health` | Liveness/readiness probe |
| `GET /metrics` | Prometheus metrics |

## Monitoring

```bash
# Port-forward Grafana to localhost:3000
make grafana-port-forward   # in a separate terminal

# Get password (or use 'admin' — set during make setup)
make grafana-password
```

Import dashboards from `grafana/`:
1. `grafana/envoy-dashboard.json` — aggregate throughput, latency p50/p95/p99, error rate, active connections
2. `grafana/worker-dashboard.json` — per-pod request rate, active in-flight requests, latency by pod, distribution bar chart

## Running Experiments

### Full suite (~45–60 min)

```bash
make experiments   # all 4 policies × 4 scenarios + fault injection
make results       # generate figures and tables in results/
```

### Single experiment

```bash
bash experiments/run_experiment.sh least-request heavy
```

Available policies: `rr`, `least-request`, `ring-hash`, `maglev`  
Available scenarios: `steady`, `burst`, `heavy`, `spike`

### Fault injection only

```bash
bash experiments/fault_injection.sh rr
bash experiments/fault_injection.sh least-request
```

### Results

After running experiments, `results/` contains:

| File | Description |
|------|-------------|
| `k6-{policy}-{scenario}.json` | Raw k6 metric stream |
| `prom-{policy}-{scenario}.json` | Prometheus latency/throughput snapshot |
| `fault-{policy}.json` | Recovery time from pod deletion |
| `log-{policy}-{scenario}.txt` | k6 stdout |
| `fig_latency_comparison.png` | p50/p95/p99 grouped bar chart |
| `fig_throughput_comparison.png` | Throughput by policy |
| `fig_error_rate.png` | Error rate by policy |
| `fig_fault_recovery.png` | Recovery time comparison |
| `fig_pod_distribution.png` | Per-pod request share |
| `summary.md` | Markdown results table |
| `summary_tex.tex` | LaTeX table (paste into IEEE paper) |

## Optional: Autoscaling Extension

```bash
make hpa
# Watch HPA scale the worker deployment under load:
kubectl -n dlb get hpa -w
```

The HPA scales `dlb-worker` between 2 and 6 replicas when CPU utilisation exceeds 70%.

## Reproducing From Scratch

```bash
git clone <repo>
cd project
make setup    # ~3 min
make deploy   # ~2 min
make test     # ~1 min
make experiments   # ~45–60 min
make results
```

Fixed random seeds are not applicable (k6 uses wall-clock time for VU scheduling). Re-runs on the same cluster converge to equivalent distributions within ±5%.
