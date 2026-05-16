#!/usr/bin/env python3
"""Generate paper-quality figures from k6 JSON results for the IEEE paper."""

import json
import os
import sys
import glob

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "paper", "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

# --- IEEE figure aesthetics ---
SINGLE_COL_IN = 3.5
DOUBLE_COL_IN = 7.16
FIG_HEIGHT = 2.4
FONT_SIZE = 8
plt.rcParams.update({
    "font.size": FONT_SIZE,
    "font.family": "serif",
    "axes.labelsize": FONT_SIZE,
    "xtick.labelsize": FONT_SIZE,
    "ytick.labelsize": FONT_SIZE,
    "legend.fontsize": FONT_SIZE - 1,
    "axes.linewidth": 0.6,
    "lines.linewidth": 0.8,
    "patch.linewidth": 0.5,
    "figure.dpi": 200,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

POLICIES = ["rr", "least-request", "ring-hash", "maglev"]
POLICY_LABELS = ["Round Robin", "Least Request", "Ring Hash", "Maglev"]
SCENARIOS = ["steady", "burst", "heavy", "spike"]

# B&W-safe hatch patterns + colours
HATCHES = ["", "///", "xxx", "..."]
COLORS = ["#ffffff", "#aaaaaa", "#555555", "#000000"]
EDGE_COLORS = ["#000000"] * 4


def extract_k6_metrics(path):
    """Return (p50_ms, p95_ms, p99_ms, rps, error_rate_pct) from a k6 JSON summary."""
    if not os.path.exists(path):
        return None
    try:
        # k6 JSON output has one metric object per line; look for the http_req_duration summary
        p50 = p95 = p99 = rps = err_rate = None
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "Point":
                    continue
                metric = obj.get("metric", "")
                data = obj.get("data", {})
                if metric == "http_req_duration" and obj.get("type") == "Metric":
                    continue
                if obj.get("type") == "Metric" and metric == "http_reqs":
                    rps = data.get("contains", {})
                # Aggregated summary lines have type==Summary or are in the summary block
                if obj.get("type") == "Point" and metric == "http_req_duration":
                    pass
            # Re-parse to find the summary-style aggregated metrics
            f.seek(0) if hasattr(f, "seek") else None

        # Parse using k6 summary format (aggregated at end)
        durations = []
        total_requests = 0
        failed_requests = 0
        with open(path) as f:
            content = f.read()

        # k6 --out json writes one JSON object per line (streaming format)
        lines = content.strip().split("\n")
        dur_values = []
        req_count = 0
        fail_count = 0
        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = obj.get("type", "")
            metric = obj.get("metric", "")
            d = obj.get("data", {})
            val = d.get("value", 0)
            if t == "Point":
                if metric == "http_req_duration":
                    dur_values.append(float(val))
                elif metric == "http_reqs":
                    req_count += 1
                elif metric == "http_req_failed":
                    fail_count += float(val)

        if not dur_values:
            return None
        arr = np.array(dur_values)
        p50 = float(np.percentile(arr, 50))
        p95 = float(np.percentile(arr, 95))
        p99 = float(np.percentile(arr, 99))
        rps = req_count / max(1, (len(dur_values) / max(1, req_count))) if req_count else len(dur_values) / 60.0
        # Better RPS estimate: count data points (one per request) divided by experiment duration
        # We'll use a simpler approach: total data points / duration from timestamps
        if dur_values:
            rps = len(dur_values) / 60.0  # rough: most scenarios run ~60s or we normalise later
        err_rate = 100.0 * fail_count / max(1, len(dur_values))
        return p50, p95, p99, rps, err_rate
    except Exception as e:
        print(f"  WARNING: failed to parse {path}: {e}", file=sys.stderr)
        return None


def get_rps_from_k6(path, duration_s=60):
    """Estimate req/s from total data points and duration."""
    if not os.path.exists(path):
        return None
    count = 0
    with open(path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "Point" and obj.get("metric") == "http_req_duration":
                count += 1
    return count / duration_s if count else None


def load_all_metrics():
    """Return dict[policy][scenario] = (p50, p95, p99, rps, err_pct)."""
    durations = {"steady": 90, "burst": 90, "heavy": 180, "spike": 50, "fault": 60}
    data = {}
    for policy in POLICIES:
        data[policy] = {}
        for scenario in SCENARIOS:
            path = os.path.join(RESULTS_DIR, f"k6-{policy}-{scenario}.json")
            m = extract_k6_metrics(path)
            if m:
                p50, p95, p99, _, err = m
                rps = get_rps_from_k6(path, durations.get(scenario, 60))
                data[policy][scenario] = (p50, p95, p99, rps, err)
            else:
                data[policy][scenario] = None
    return data


def load_fault_data():
    """Return dict[policy] = recovery_time_s."""
    result = {}
    for policy in POLICIES:
        path = os.path.join(RESULTS_DIR, f"fault-{policy}.json")
        if os.path.exists(path):
            with open(path) as f:
                obj = json.load(f)
            result[policy] = obj.get("recovery_time_s", 0)
    return result


# ---- Figure 1: p95 Latency grouped bar chart ----
def fig_p95_latency(data):
    fig, ax = plt.subplots(figsize=(DOUBLE_COL_IN, FIG_HEIGHT))
    n_scenarios = len(SCENARIOS)
    n_policies = len(POLICIES)
    group_w = 0.7
    bar_w = group_w / n_policies
    x = np.arange(n_scenarios)

    for i, (policy, label) in enumerate(zip(POLICIES, POLICY_LABELS)):
        vals = []
        for sc in SCENARIOS:
            m = data[policy].get(sc)
            vals.append(m[1] if m else 0)  # p95
        offset = (i - n_policies / 2 + 0.5) * bar_w
        bars = ax.bar(x + offset, vals, bar_w,
                      label=label,
                      color=COLORS[i],
                      edgecolor=EDGE_COLORS[i],
                      hatch=HATCHES[i],
                      linewidth=0.5)

    ax.set_xlabel("Load Scenario")
    ax.set_ylabel("p95 Latency (ms)")
    ax.set_xticks(x)
    ax.set_xticklabels([s.capitalize() for s in SCENARIOS])
    ax.legend(loc="upper right", framealpha=0.9, ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.7)
    ax.set_axisbelow(True)
    fig.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig_p95_latency.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"))
    plt.close(fig)
    print(f"  saved {out}")


# ---- Figure 2: Throughput grouped bar chart ----
def fig_throughput(data):
    fig, ax = plt.subplots(figsize=(DOUBLE_COL_IN, FIG_HEIGHT))
    n_scenarios = len(SCENARIOS)
    n_policies = len(POLICIES)
    group_w = 0.7
    bar_w = group_w / n_policies
    x = np.arange(n_scenarios)

    for i, (policy, label) in enumerate(zip(POLICIES, POLICY_LABELS)):
        vals = []
        for sc in SCENARIOS:
            m = data[policy].get(sc)
            vals.append(m[3] if (m and m[3] is not None) else 0)
        offset = (i - n_policies / 2 + 0.5) * bar_w
        ax.bar(x + offset, vals, bar_w,
               label=label,
               color=COLORS[i],
               edgecolor=EDGE_COLORS[i],
               hatch=HATCHES[i],
               linewidth=0.5)

    ax.set_xlabel("Load Scenario")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_xticks(x)
    ax.set_xticklabels([s.capitalize() for s in SCENARIOS])
    ax.legend(loc="upper right", framealpha=0.9, ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.7)
    ax.set_axisbelow(True)
    fig.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig_throughput.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"))
    plt.close(fig)
    print(f"  saved {out}")


# ---- Figure 3: Fault recovery + error spike ----
def fig_fault_recovery(fault_data):
    fig, ax = plt.subplots(figsize=(SINGLE_COL_IN, FIG_HEIGHT))
    n = len(POLICIES)
    x = np.arange(n)
    vals = [fault_data.get(p, 0) for p in POLICIES]
    bars = ax.bar(x, vals, 0.55,
                  color=COLORS,
                  edgecolor=EDGE_COLORS,
                  hatch=HATCHES,
                  linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(["RR", "Least\nReq", "Ring\nHash", "Maglev"], fontsize=FONT_SIZE - 1)
    ax.set_ylabel("Recovery Time (s)")
    ax.set_ylim(0, max(vals) * 1.4 + 0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{v}s", ha="center", va="bottom", fontsize=FONT_SIZE - 1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.7)
    ax.set_axisbelow(True)
    fig.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig_fault_recovery.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"))
    plt.close(fig)
    print(f"  saved {out}")


# ---- Figure 4: p50 vs p95 scatter ----
def fig_p50_vs_p95(data):
    fig, ax = plt.subplots(figsize=(SINGLE_COL_IN, FIG_HEIGHT))
    markers = ["o", "s", "^", "D"]
    for i, (policy, label) in enumerate(zip(POLICIES, POLICY_LABELS)):
        xs, ys = [], []
        for sc in SCENARIOS:
            m = data[policy].get(sc)
            if m:
                xs.append(m[0])  # p50
                ys.append(m[1])  # p95
        ax.scatter(xs, ys, marker=markers[i], label=label,
                   s=28, color=COLORS[i] if COLORS[i] != "#ffffff" else "#333333",
                   edgecolors="black", linewidths=0.5, zorder=3)
    ax.set_xlabel("p50 Latency (ms)")
    ax.set_ylabel("p95 Latency (ms)")
    ax.legend(loc="upper left", framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.7)
    ax.set_axisbelow(True)
    fig.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig_p50_vs_p95.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"))
    plt.close(fig)
    print(f"  saved {out}")


# ---- Figure 5: Error rate heatmap ----
def fig_error_rate(data):
    fig, ax = plt.subplots(figsize=(SINGLE_COL_IN + 0.5, FIG_HEIGHT))
    matrix = []
    for policy in POLICIES:
        row = []
        for sc in SCENARIOS:
            m = data[policy].get(sc)
            row.append(m[4] if m else 0.0)
        matrix.append(row)
    mat = np.array(matrix)
    im = ax.imshow(mat, cmap="Greys", aspect="auto", vmin=0, vmax=max(0.5, mat.max()))
    ax.set_xticks(range(len(SCENARIOS)))
    ax.set_xticklabels([s.capitalize() for s in SCENARIOS])
    ax.set_yticks(range(len(POLICIES)))
    ax.set_yticklabels(POLICY_LABELS)
    for i in range(len(POLICIES)):
        for j in range(len(SCENARIOS)):
            val = mat[i, j]
            color = "white" if val > mat.max() * 0.6 else "black"
            ax.text(j, i, f"{val:.2f}%", ha="center", va="center",
                    fontsize=FONT_SIZE - 2, color=color)
    ax.set_xlabel("Scenario")
    plt.colorbar(im, ax=ax, label="Error Rate (%)", fraction=0.046, pad=0.04)
    fig.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig_error_rate.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"))
    plt.close(fig)
    print(f"  saved {out}")


if __name__ == "__main__":
    print("Loading k6 metrics...")
    data = load_all_metrics()
    print("Loading fault data...")
    fault_data = load_fault_data()

    # Print summary
    print("\nData summary (p50 / p95 / p99 ms, rps, err%):")
    print(f"{'Policy':<16} {'Scenario':<10} {'p50':>8} {'p95':>8} {'p99':>8} {'rps':>8} {'err%':>8}")
    for policy in POLICIES:
        for sc in SCENARIOS:
            m = data[policy].get(sc)
            if m:
                print(f"{policy:<16} {sc:<10} {m[0]:>8.1f} {m[1]:>8.1f} {m[2]:>8.1f} "
                      f"{m[3]:>8.1f} {m[4]:>8.2f}")

    print("\nGenerating figures...")
    fig_p95_latency(data)
    fig_throughput(data)
    fig_fault_recovery(fault_data)
    fig_p50_vs_p95(data)
    fig_error_rate(data)

    print("\nDone. Figures saved to paper/figures/")
