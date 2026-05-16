#!/usr/bin/env python3
"""Generate Markdown and LaTeX summary tables from experiment results."""

import json
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "results"
POLICIES  = ["rr", "least-request", "ring-hash", "maglev"]
SCENARIOS = ["steady", "burst", "heavy", "spike"]
POLICY_LABELS = {
    "rr":             "Round Robin",
    "least-request":  "Least Request",
    "ring-hash":      "Ring Hash",
    "maglev":         "Maglev",
}


def load_prom(policy, scenario):
    path = RESULTS_DIR / f"prom-{policy}-{scenario}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def fmt(v, decimals=1):
    if v is None or v == "null" or v == 0:
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except (ValueError, TypeError):
        return "—"


def build_rows():
    rows = []
    for policy in POLICIES:
        for scenario in SCENARIOS:
            prom = load_prom(policy, scenario)
            lat = prom.get("latency_ms", {})
            rows.append({
                "policy":   POLICY_LABELS[policy],
                "scenario": scenario,
                "p50":      lat.get("p50"),
                "p95":      lat.get("p95"),
                "p99":      lat.get("p99"),
                "rps":      prom.get("throughput_rps"),
                "err5xx":   prom.get("errors_5xx_rps"),
            })
    return rows


def write_markdown(rows):
    header = "| Policy | Scenario | p50 (ms) | p95 (ms) | p99 (ms) | RPS | 5xx/s |"
    sep    = "|--------|----------|----------|----------|----------|-----|-------|"
    lines  = [header, sep]
    for r in rows:
        lines.append(
            f"| {r['policy']} | {r['scenario']} "
            f"| {fmt(r['p50'])} | {fmt(r['p95'])} | {fmt(r['p99'])} "
            f"| {fmt(r['rps'])} | {fmt(r['err5xx'], 3)} |"
        )
    out = RESULTS_DIR / "summary.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"Saved: {out}")


def write_latex(rows):
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Load-Balancing Algorithm Comparison}",
        r"\label{tab:results}",
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Policy & Scenario & p50 (ms) & p95 (ms) & p99 (ms) & RPS & 5xx/s \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(
            f"{r['policy']} & {r['scenario']} & "
            f"{fmt(r['p50'])} & {fmt(r['p95'])} & {fmt(r['p99'])} & "
            f"{fmt(r['rps'])} & {fmt(r['err5xx'], 3)} \\\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    out = RESULTS_DIR / "summary_tex.tex"
    out.write_text("\n".join(lines) + "\n")
    print(f"Saved: {out}")


if __name__ == "__main__":
    rows = build_rows()
    write_markdown(rows)
    write_latex(rows)
    print("Done.")
