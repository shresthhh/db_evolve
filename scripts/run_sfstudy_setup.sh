#!/usr/bin/env bash
# Scale-factor study setup (plan.md, Phase 2c): data at SF 1/3/10/30/100 plus shadow SF 2, references,
# baseline timing of the 110 items, and per-item noise calibration. Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
C="--config config/tpch-sf.toml"
step() { echo "[$(date +%H:%M:%S)] ##### $*"; }
step "setup: datasets, databases, references"; bin/dbe $C setup || exit 1
step "baseline"; bin/dbe $C baseline || exit 1
step "calibrate"; bin/dbe $C calibrate || exit 1
step "done"
