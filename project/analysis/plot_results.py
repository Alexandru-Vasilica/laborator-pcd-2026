#!/usr/bin/env python3
"""Generate comparison figures from k6 JSON and Prometheus JSON outputs."""

import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = Path(__file__).parent.parent / "results"
POLICIES  = ["rr", "least-request", "ring-hash", "maglev"]
SCENARIOS = ["steady", "burst", "heavy", "spike"]
POLICY_LABELS = {
    "rr":             "Round Robin",
    "least-request":  "Least Request",
    "ring-hash":      "Ring Hash",
    "maglev":         "Maglev",
}


def load_prom(policy: str, scenario: str) -> dict:
    path = RESULTS_DIR / f"prom-{policy}-{scenario}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def load_k6(policy: str, scenario: str) -> dict:
    """Parse k6 JSON summary output for p95 latency and throughput."""
    path = RESULTS_DIR / f"k6-{policy}-{scenario}.json"
    if not path.exists():
        return {}
    metrics: dict = {"p95_ms": None, "rps": None, "error_rate": None}
    # k6 --out json emits one metric object per line
    p95_vals, durations = [], []
    errors, totals = 0, 0
    with open(path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "Point":
                m = obj.get("metric", "")
                v = obj.get("data", {}).get("value", 0)
                if m == "http_req_duration":
                    durations.append(v)
                elif m == "http_reqs":
                    totals += 1
                elif m == "http_req_failed" and v > 0:
                    errors += 1
    if durations:
        metrics["p95_ms"] = float(np.percentile(durations, 95))
        metrics["p50_ms"] = float(np.percentile(durations, 50))
        metrics["p99_ms"] = float(np.percentile(durations, 99))
    if totals:
        metrics["error_rate"] = errors / totals
    return metrics


def fig_latency_bar():
    """Grouped bar chart: p50/p95/p99 latency per policy, one subplot per scenario."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    for ax, scenario in zip(axes, SCENARIOS):
        p50s, p95s, p99s = [], [], []
        labels = []
        for policy in POLICIES:
            prom = load_prom(policy, scenario)
            k6   = load_k6(policy, scenario)
            # Prefer Prometheus (server-side); fall back to k6 (client-side)
            lat = prom.get("latency_ms", {})
            p50 = lat.get("p50") or k6.get("p50_ms") or 0
            p95 = lat.get("p95") or k6.get("p95_ms") or 0
            p99 = lat.get("p99") or k6.get("p99_ms") or 0
            p50s.append(float(p50) if p50 != "null" else 0)
            p95s.append(float(p95) if p95 != "null" else 0)
            p99s.append(float(p99) if p99 != "null" else 0)
            labels.append(POLICY_LABELS[policy])

        x = np.arange(len(labels))
        w = 0.25
        ax.bar(x - w,  p50s, w, label="p50",  color="#4e9af1")
        ax.bar(x,      p95s, w, label="p95",  color="#f4a261")
        ax.bar(x + w,  p99s, w, label="p99",  color="#e76f51")
        ax.set_title(f"Latency — {scenario}", fontsize=12)
        ax.set_ylabel("Latency (ms)")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=15, ha="right")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Latency Comparison by Policy and Scenario", fontsize=14, fontweight="bold")
    fig.tight_layout()
    out = RESULTS_DIR / "fig_latency_comparison.png"
    fig.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close(fig)


def fig_throughput_bar():
    """Bar chart: average throughput (req/s) per policy, grouped by scenario."""
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(SCENARIOS))
    n = len(POLICIES)
    w = 0.8 / n
    colors = ["#4e9af1", "#57cc99", "#f4a261", "#e76f51"]

    for i, (policy, color) in enumerate(zip(POLICIES, colors)):
        rps_vals = []
        for scenario in SCENARIOS:
            prom = load_prom(policy, scenario)
            rps = prom.get("throughput_rps", 0)
            rps_vals.append(float(rps) if rps and rps != "null" else 0)
        offset = (i - n / 2 + 0.5) * w
        ax.bar(x + offset, rps_vals, w, label=POLICY_LABELS[policy], color=color)

    ax.set_title("Throughput (req/s) by Policy and Scenario", fontsize=14, fontweight="bold")
    ax.set_ylabel("Requests / second")
    ax.set_xticks(x)
    ax.set_xticklabels(SCENARIOS)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = RESULTS_DIR / "fig_throughput_comparison.png"
    fig.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close(fig)


def fig_error_rate():
    """Bar chart: error rate per policy, grouped by scenario."""
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(SCENARIOS))
    n = len(POLICIES)
    w = 0.8 / n
    colors = ["#4e9af1", "#57cc99", "#f4a261", "#e76f51"]

    for i, (policy, color) in enumerate(zip(POLICIES, colors)):
        err_vals = []
        for scenario in SCENARIOS:
            k6 = load_k6(policy, scenario)
            err_vals.append((k6.get("error_rate") or 0) * 100)
        offset = (i - n / 2 + 0.5) * w
        ax.bar(x + offset, err_vals, w, label=POLICY_LABELS[policy], color=color)

    ax.set_title("Error Rate (%) by Policy and Scenario", fontsize=14, fontweight="bold")
    ax.set_ylabel("Error rate (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(SCENARIOS)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = RESULTS_DIR / "fig_error_rate.png"
    fig.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close(fig)


def fig_fault_recovery():
    """Bar chart: pod recovery time per policy after fault injection."""
    recovery_times = {}
    for policy in POLICIES:
        path = RESULTS_DIR / f"fault-{policy}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            recovery_times[policy] = data.get("recovery_time_s", 0)

    if not recovery_times:
        print("No fault injection results found — skipping recovery chart.")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [POLICY_LABELS[p] for p in POLICIES if p in recovery_times]
    values = [recovery_times[p] for p in POLICIES if p in recovery_times]
    colors = ["#4e9af1", "#57cc99", "#f4a261", "#e76f51"][:len(values)]
    ax.bar(labels, values, color=colors)
    ax.set_title("Pod Recovery Time After Fault Injection", fontsize=14, fontweight="bold")
    ax.set_ylabel("Recovery time (s)")
    ax.grid(axis="y", alpha=0.3)
    for i, v in enumerate(values):
        ax.text(i, v + 0.3, f"{v}s", ha="center", fontsize=11)
    fig.tight_layout()
    out = RESULTS_DIR / "fig_fault_recovery.png"
    fig.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close(fig)


def fig_pod_distribution():
    """Line chart: per-pod request totals from worker metrics (if available)."""
    # Requires Prometheus data with per-pod worker_requests_total
    # This figure is generated from a manual Prometheus range query output
    # saved as results/pod-distribution.json by the user or collect script.
    path = RESULTS_DIR / "pod-distribution.json"
    if not path.exists():
        print("No pod-distribution.json found — skipping pod distribution chart.")
        return
    with open(path) as f:
        data = json.load(f)

    fig, axes = plt.subplots(1, len(data), figsize=(4 * len(data), 5), sharey=True)
    if len(data) == 1:
        axes = [axes]
    colors = ["#4e9af1", "#57cc99", "#f4a261", "#e76f51", "#c77dff"]

    for ax, (policy, pods) in zip(axes, data.items()):
        pod_names = list(pods.keys())
        counts = list(pods.values())
        ax.bar(range(len(pod_names)), counts,
               color=colors[:len(pod_names)])
        ax.set_title(POLICY_LABELS.get(policy, policy), fontsize=11)
        ax.set_xticks(range(len(pod_names)))
        ax.set_xticklabels([p.split("-")[-1] for p in pod_names], rotation=30)
        ax.set_xlabel("Pod (suffix)")
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("Total requests")
    fig.suptitle("Request Distribution per Pod by Policy", fontsize=14, fontweight="bold")
    fig.tight_layout()
    out = RESULTS_DIR / "fig_pod_distribution.png"
    fig.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close(fig)


if __name__ == "__main__":
    print(f"Reading results from: {RESULTS_DIR}")
    fig_latency_bar()
    fig_throughput_bar()
    fig_error_rate()
    fig_fault_recovery()
    fig_pod_distribution()
    print("Done.")
