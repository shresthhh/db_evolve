#!/usr/bin/env bash
# Controls for the specialisation pilot (see plan.md, Phase 2b pilot findings):
#  1. replicates: q09, q13, q16 specialised again from v0 (runs rep-<t>), to measure run-to-run spread;
#  2. equal-effort joint evolution: 3 generations x 16 rounds = 48 experiments (run joint48), the same
#     effort as the eight specialisations together;
#  3. reports: joint48 by release (effort curve), then one cross-evaluation of every engine involved.
# Every step resumes work already done, so the script can be re-run after an interruption.
set -uo pipefail
cd "$(dirname "$0")/.."
step() { echo "[$(date +%H:%M:%S)] ##### $*"; }
PY=.toolchain/env/bin/python

step "1. replicate specialisations q09 q13 q16 (6 rounds each)"
bin/dbe specialize q09 q13 q16 --rounds 6 --prefix rep || exit 1

step "2. joint evolution with equal effort (3 x 16 rounds)"
$PY -c "
from dbevolve import config
base = config.load(None)
config.derive(base, {'engine': {'branch': 'dbe/joint48', 'tag_prefix': 'dbe/joint48'}},
              base.work / 'configs' / 'joint48.toml')
" || exit 1
bin/dbe --config work/configs/joint48.toml evolve --run joint48 --generations 3 --rounds 16 || exit 1

step "3a. joint48 releases v0-v3 on all templates"
bin/dbe report --run joint48 || exit 1

step "3b. cross-evaluate replicates, originals, joint runs and the merged engine"
bin/dbe crosseval --prefix rep --also spec-q09,spec-q13,spec-q16,sf10,joint48,merge-agent-k1-g1 --out controls || exit 1
step "done"
