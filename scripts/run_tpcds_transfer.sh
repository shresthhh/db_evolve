#!/usr/bin/env bash
# TPC-DS generalisation: time each TPC-H run's releases on all 99 TPC-DS templates (SF 10).
# No agents. Runs whose state is not present (e.g. joint48 before it is copied over) are skipped.
set -uo pipefail
cd "$(dirname "$0")/.."
step() { echo "[$(date +%H:%M:%S)] ##### $*"; }
for run in ${RUNS:-sf10 merge-agent-k1-g1 joint48}; do
  if [ ! -f "runs/$run/state.json" ]; then step "skip $run (no run state here)"; continue; fi
  out="$run-tpcds-$(hostname -s)"   # per machine: timings only compare within one machine
  if [ -f "results/$out/report.json" ]; then step "skip $run (already done)"; continue; fi
  step "TPC-DS transfer of $run -> results/$out"
  bin/dbe --config config/tpcds.toml transfer --run "$run" --out "$out" || exit 1
done
step "done"
