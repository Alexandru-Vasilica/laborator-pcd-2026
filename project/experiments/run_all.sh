#!/usr/bin/env bash
# run_all.sh — run all policy × scenario combinations and print a summary.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$ROOT/results"
mkdir -p "$RESULTS_DIR"

POLICIES=(rr least-request ring-hash maglev)
SCENARIOS=(steady burst heavy spike)

echo "========================================"
echo " DLB Full Experiment Suite"
echo " $(date)"
echo "========================================"

FAILED=()

for policy in "${POLICIES[@]}"; do
  for scenario in "${SCENARIOS[@]}"; do
    echo ""
    echo "-------- $policy / $scenario --------"
    if "$ROOT/experiments/run_experiment.sh" "$policy" "$scenario"; then
      echo "OK: $policy/$scenario"
    else
      echo "FAILED: $policy/$scenario" >&2
      FAILED+=("$policy/$scenario")
    fi
  done
done

echo ""
echo "========================================"
echo " Fault Injection Experiments"
echo "========================================"
for policy in "${POLICIES[@]}"; do
  echo ""
  echo "-------- fault: $policy --------"
  if "$ROOT/experiments/fault_injection.sh" "$policy"; then
    echo "OK: fault/$policy"
  else
    echo "FAILED: fault/$policy" >&2
    FAILED+=("fault/$policy")
  fi
done

echo ""
echo "========================================"
echo " Summary"
echo "========================================"
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "All experiments completed successfully."
else
  echo "Failed experiments:"
  for f in "${FAILED[@]}"; do echo "  - $f"; done
fi
echo ""
echo "Results saved to: $RESULTS_DIR"
echo "Run 'make results' to generate figures and tables."
