#!/usr/bin/env bash
# Scale-factor study runs (plan.md, Phase 2c). Every step resumes work already done.
#  1. joint evolution on the 80 visible (template, SF) items: 3 generations x 16 rounds (run sfjoint)
#  2. its releases on all 110 items (train / val / test)
#  3. one specialised run per scale factor (16 rounds on that SF's visible items), for the SF x SF matrix
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.toolchain/env/bin/python
C=config/tpch-sf.toml
step() { echo "[$(date +%H:%M:%S)] ##### $*"; }

step "1. joint evolution over the 80 visible items (3 x 16 rounds)"
bin/dbe --config $C evolve --run sfjoint --generations 3 --rounds 16 || exit 1
step "2. sfjoint releases on all 110 items"
bin/dbe --config $C report --run sfjoint || exit 1

for lab in sf1 sf3 sf10 sf30 sf100; do
  step "3. specialised run at $lab"
  $PY - "$lab" <<'PYEOF' || exit 1
import sys
from dbevolve import config
from dbevolve.workload import Workload
lab = sys.argv[1]
base = config.load(config.ROOT / "config" / "tpch-sf.toml")
items = [i for i in Workload(base).split["train"] if i.endswith("@" + lab)]
config.derive(base, {"workload": {"focus": items},
                     "engine": {"branch": f"dbe/sfspec/{lab}", "tag_prefix": f"dbe/sfspec/{lab}"}},
              base.work / "configs" / f"sfspec-{lab}.toml")
print(f"{lab}: {len(items)} visible items")
PYEOF
  bin/dbe --config work/configs/sfspec-$lab.toml evolve --run sfspec-$lab --generations 1 --rounds 16 || exit 1
done
step "done (next: cross-evaluate sfjoint and the five sfspec engines on all 110 items)"
