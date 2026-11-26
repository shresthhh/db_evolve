#!/usr/bin/env bash
# Changelog + generality audit of every run's releases (resumes; one auditor call per change).
set -uo pipefail
cd "$(dirname "$0")/.."
for run in ${RUNS:-sf10 merge-agent-k1-g1 spec-q01 spec-q02 spec-q09 spec-q13 spec-q16 spec-q18 spec-q19 spec-q21 rep-q09 rep-q13 rep-q16 joint48}; do
  [ -f "runs/$run/state.json" ] || { echo "skip $run (no run state here)"; continue; }
  echo "[$(date +%H:%M:%S)] ##### audit $run"
  bin/dbe audit --run "$run" || echo "audit of $run failed"
done
