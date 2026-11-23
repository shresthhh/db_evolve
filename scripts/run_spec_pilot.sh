#!/usr/bin/env bash
# Specialisation pilot: 8 TPC-H templates, k = 1, 2, 4, 8. See docs/specialization-study.md.
# Waits for the TPC-DS transfer test, checks the merge step with the scripted agent, then runs
# every step. Each step resumes or skips work that is already done, so the script can be re-run.
set -uo pipefail
cd "$(dirname "$0")/.."
L=work/logs
T="q01 q02 q09 q13 q16 q18 q19 q21"
step() { echo "[$(date +%H:%M:%S)] ##### $*"; }

step "waiting for the TPC-DS transfer test to finish"
while [ -f $L/sf10-tpcds.log ] && ! grep -q '^exit=' $L/sf10-tpcds.log; do sleep 60; done

step "merge self-test (scripted agent, no model calls)"
.toolchain/env/bin/python scripts/merge_selftest.py > $L/merge-selftest.log 2>&1 \
  || { step "merge self-test FAILED; stopping (see $L/merge-selftest.log)"; exit 1; }

step "1. specialise $T (6 rounds each)"
bin/dbe specialize $T --rounds 6 || { step "specialise failed"; exit 1; }

step "2. cross-evaluate the specialised systems"
bin/dbe crosseval --prefix spec --out spec-cross || exit 1

step "3. agent chooses groups for k = 1 2 4 8"
bin/dbe groups $T --k 1 2 4 8 || exit 1

step "4. merge each group"
bin/dbe merge-groups --k 1 2 4 8 || exit 1

step "5. cross-evaluate everything (specialised, merged, v0, joint-evolution v3)"
bin/dbe crosseval --prefix spec --with-merges --also sf10 --out spec-cross-merged || exit 1

step "6. curve"
bin/dbe curve
step "done"
