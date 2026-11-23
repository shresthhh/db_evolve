"""Merge step end to end with the scripted agent (no model calls), on two known changes.
Exit 0 if a merged engine came out of the gates; cleans up after itself."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["DBE_AGENT_BACKEND"] = "mock"
from dbevolve import config
from dbevolve.engine import Engine
from dbevolve.loop import Loop, Run

base = config.load()
cfg = config.derive(base, {"workload": {"focus": ["q09", "q19"]},
                           "engine": {"branch": "dbe/merge/selftest", "tag_prefix": "dbe/merge/selftest"}},
                    base.work / "configs" / "merge-selftest.toml")
e = Engine(cfg)
shutil.rmtree(cfg.runs / "merge-selftest", ignore_errors=True)
e.accept(e.base_sha())
run = Run.create(cfg, "merge-selftest", e.base_sha())
srcs = {"q09": e.git("rev-parse", "dbe/ablate/sf10/only-E0008"), "q19": e.git("rev-parse", "dbe/ablate/sf10/only-E0010")}
rec = Loop(cfg, run).merge(srcs)
merged = run.state.get("merged_sha")
print("SELFTEST", rec.get("outcome"), rec.get("reasons"), "merged", merged, run.state["merge"])
ok = bool(merged) and run.state["merge"]["applied"] == ["q09", "q19"]
shutil.copytree(cfg.runs / "merge-selftest", cfg.work / "logs" / "merge-selftest-run", dirs_exist_ok=True)
shutil.rmtree(cfg.runs / "merge-selftest", ignore_errors=True)
e.git("branch", "-D", "dbe/merge/selftest", check=False)
sys.exit(0 if ok else 1)
