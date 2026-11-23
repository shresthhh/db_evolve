"""Unit tests for the parts that need no engine build. Run: .toolchain/env/bin/python -m pytest -q"""
import json
import random

import pytest

from dbevolve import bench, compare, config, gates
from dbevolve.agents import parse_cli_output
from dbevolve.workload import Workload, tpch

BAR = {"min_gain": 0.02, "noise_multiplier": 2.0, "max_template_regression": 0.10, "abs_slack_ms": 5.0,
       "val_tolerance": 0.02, "rule": "geomean"}
TBAR = {**BAR, "rule": "templates", "min_template_gain": 0.05, "max_template_regression": 0.05,
        "max_geomean_regression": 0.0}


@pytest.fixture(scope="module")
def wl():
    return Workload(config.load())


def test_every_template_instantiates_fully():
    for t in tpch.TEMPLATES:
        for seed in range(25):
            sql, params = tpch.instantiate(t, random.Random(seed), 1.0)
            assert "{" not in sql and "}" not in sql and "\n" not in sql
            assert sql.upper().startswith(("SELECT", "WITH"))
            assert params


def test_parameters_follow_the_spec_ranges():
    r = random.Random(1)
    for _ in range(200):
        assert 60 <= tpch._p1(r, 1)["delta"] <= 120
        assert tpch._p4(r, 1)["date"][:4] in {"1993", "1994", "1995", "1996", "1997"}
        p7 = tpch._p7(r, 1)
        assert p7["nation1"] != p7["nation2"]
        p8 = tpch._p8(r, 1)
        assert tpch.NATIONS[p8["nation"]] == p8["region"]
        assert len(set(tpch._p16(r, 1)["sizes"].split(", "))) == 8
        assert len(set(tpch._p22(r, 1)["codes"].split(", "))) == 7
    assert len(tpch.COLORS) == 92 and len(tpch.NATIONS) == 25
    assert tpch._p11(r, 0.1)["fraction"] == "0.0010000000"


def test_split_is_disjoint_complete_and_stable(wl):
    s = wl.split
    all_ = s["train"] + s["val"] + s["test"]
    assert sorted(all_) == sorted(tpch.TEMPLATES) and len(set(all_)) == 22
    assert (len(s["train"]), len(s["val"]), len(s["test"])) == (14, 3, 5)
    assert Workload(config.load()).split == s


def test_bindings_are_deterministic_and_heldout_differs(wl):
    a, b = wl.instances("train", 1.0), wl.instances("train", 1.0)
    assert [i.sql for i in a] == [i.sql for i in b]
    held = wl.instances("train", 1.0, heldout=True)
    assert {i.template for i in held} == set(wl.split["train"])
    assert {i.id for i in held}.isdisjoint({i.id for i in a})


def test_gate_instances_never_include_test_templates(wl):
    used = {i.template for group in wl.gate_instances(1.0).values() for i in group}
    assert used.isdisjoint(wl.split["test"])


def test_compare_is_ordered_and_tolerant_only_on_numbers():
    assert compare.equal("a,b\n1,x\n", "a,b\n1,x\n")[0]
    assert compare.equal("a\n0.30000000000000004\n", "a\n0.3\n")[0]
    assert not compare.equal("a\n0.31\n", "a\n0.3\n")[0]
    assert not compare.equal("a\n1\n2\n", "a\n2\n1\n")[0]          # order matters
    assert not compare.equal("a\n1\n", "a\n1\n1\n")[0]             # row count matters
    assert not compare.equal("a\nx\n", "a\ny\n")[0]


def test_static_audit_flags_only_added_workload_identifiers():
    diff = "\n".join([
        "+++ b/src/execution/foo.cpp",
        "+  if (name == \"lineitem\") { fast(); }",
        "-  // removed mention of l_shipdate is fine",
        "+  idx_t p_size = 0; auto s_name = x; // ordinary identifiers",
        "+++ b/src/optimizer/bar.cpp",
        "+  // tuned for TPC-H",
    ])
    found = gates.static_audit(diff, tpch.audit_patterns())
    assert len(found) == 2
    assert "foo.cpp" in found[0] and "bar.cpp" in found[1]


def test_bar_accepts_real_gain_and_rejects_noise_regressions_and_val_slowdowns():
    inc = {"a": 0.100, "b": 0.200}
    val = {"v": 0.100}
    ok = bench.decide(inc, {"a": 0.090, "b": 0.180}, val, {"v": 0.100}, BAR, {"noise": 0.005})
    assert ok["accept"] and ok["train_ratio"] == pytest.approx(0.9)
    assert not bench.decide(inc, {"a": 0.099, "b": 0.198}, val, val, BAR, {"noise": 0.005})["accept"]        # below min gain
    assert not bench.decide(inc, {"a": 0.090, "b": 0.180}, val, val, BAR, {"noise": 0.08})["accept"]   # inside noise
    d = bench.decide(inc, {"a": 0.050, "b": 0.240}, val, val, BAR, {"noise": 0.005})                         # one template +20%
    assert not d["accept"] and "b regressed" in " ".join(d["reasons"])
    d = bench.decide(inc, {"a": 0.090, "b": 0.180}, val, {"v": 0.110}, BAR, {"noise": 0.005})                # hidden slowdown
    assert not d["accept"] and not d["val_ok"]
    tiny = bench.decide({"a": 0.010, "b": 0.200}, {"a": 0.012, "b": 0.150}, val, val, BAR, {"noise": 0.005})
    assert tiny["accept"]                                                                         # +20% but only 2 ms


def test_agent_output_parsing():
    good = json.dumps({"type": "result", "is_error": False, "result": "done", "total_cost_usd": 1.5,
                       "structured_output": {"verdict": "approve"}})
    r = parse_cli_output(good)
    assert r.ok and r.output == {"verdict": "approve"} and r.cost_usd == 1.5
    r = parse_cli_output(json.dumps({"result": 'Here: {"status": "ready"}', "is_error": False}))
    assert r.ok and r.output == {"status": "ready"}
    assert not parse_cli_output("not json").ok
    assert not parse_cli_output(json.dumps({"is_error": True, "result": "budget", "subtype": "error_max_budget"})).ok


def test_template_rule_accepts_one_clear_gain_and_rejects_noise_or_regressions():
    cal = {"noise": 0.005, "val_noise": 0.005, "template_noise": {"a": 0.01, "b": 0.01, "c": 0.04, "v": 0.01}}
    inc = {"a": 0.100, "b": 0.200, "c": 0.300}
    val = {"v": 0.100}
    # one template 20 % faster, the rest flat: geomean only -7 %, accepted
    d = bench.decide(inc, {"a": 0.080, "b": 0.201, "c": 0.300}, val, val, TBAR, cal)
    assert d["accept"] and d["improved"] == ["a"]
    # 6 % faster on a template whose own noise is 4 % (threshold 8 %): not a gain
    d = bench.decide(inc, {"a": 0.100, "b": 0.200, "c": 0.282}, val, val, TBAR, cal)
    assert not d["accept"] and not d["improved"]
    # a clear gain paid for by a clear regression elsewhere: rejected
    d = bench.decide(inc, {"a": 0.080, "b": 0.220, "c": 0.300}, val, val, TBAR, cal)
    assert not d["accept"] and d["regressed"] == ["b"]
    # hidden template slower beyond its noise: rejected, and the reason does not name it
    d = bench.decide(inc, {"a": 0.080, "b": 0.200, "c": 0.300}, val, {"v": 0.110}, TBAR, cal)
    assert not d["accept"] and not d["val_ok"] and "v" not in " ".join(d["reasons"]).split()
    # borderline: retired, but a template moved half way to a gain
    d = bench.decide(inc, {"a": 0.097, "b": 0.200, "c": 0.300}, val, val, TBAR, cal)
    assert not d["accept"] and bench.borderline(d, TBAR)
    d = bench.decide(inc, {"a": 0.099, "b": 0.200, "c": 0.300}, val, val, TBAR, cal)
    assert not bench.borderline(d, TBAR)


def test_focus_mode_makes_one_template_visible_and_checks_the_rest(tmp_path):
    from dbevolve import cli, loop
    cfg = config.derive(config.load(), {"workload": {"focus": "q09"}, "engine": {"branch": "dbe/spec/q09"}},
                        tmp_path / "spec.toml")
    w = Workload(cfg)
    assert w.split["train"] == ["q09"] and not w.split["val"] and len(w.split["test"]) == 21
    g = w.gate_instances(1.0)
    assert {i.template for i in g["other"]} == set(w.split["test"]) and len(g["train"]) == 4
    assert "q09" in loop.scope_text(cfg) and loop.scope_text(config.load()) == ""
    grp = config.derive(config.load(), {"workload": {"focus": ["q13", "q01"]}}, tmp_path / "grp.toml")
    assert Workload(grp).split["train"] == ["q01", "q13"]
    assert config.load(tmp_path / "spec.toml").data == cfg.data


def test_clustering_groups_templates_that_help_each_other():
    from dbevolve import study
    m = {"a": {"a": 2.0, "b": 1.6, "c": 1.0, "d": 0.9}, "b": {"a": 1.5, "b": 2.0, "c": 1.0, "d": 1.0},
         "c": {"a": 1.0, "b": 0.95, "c": 1.5, "d": 1.4}, "d": {"a": 1.0, "b": 1.0, "c": 1.3, "d": 1.8}}
    own = {t: t for t in m}
    sim = study.similarity(m, own)
    assert study.cluster(list(own), sim, 2) == [["a", "b"], ["c", "d"]]
    assert study.cluster(list(own), sim, 4) == [["a"], ["b"], ["c"], ["d"]]
    assert study.cluster(list(own), sim, 1) == [["a", "b", "c", "d"]]
    r = study.random_groups(list(own), 2, seed=1)
    assert sorted(t for g in r for t in g) == ["a", "b", "c", "d"] and len(r) == 2
    assert study.summary(study.oracle(m, own)) == pytest.approx((2 * 2 * 1.5 * 1.8) ** 0.25)


def test_usage_limit_message_pauses_until_the_stated_reset():
    import datetime
    from zoneinfo import ZoneInfo
    from dbevolve.agents import usage_limit_pause
    now = datetime.datetime(2026, 11, 19, 14, 59, tzinfo=ZoneInfo("America/New_York"))
    msg = '{"result": "You\'ve hit your 5-hour limit · resets 3:40pm (America/New_York)", "is_error": true}'
    assert usage_limit_pause(msg, now) == 41 * 60 + 180
    late = datetime.datetime(2026, 11, 19, 23, 0, tzinfo=ZoneInfo("America/New_York"))
    assert usage_limit_pause(msg, late) == (16 * 60 + 40) * 60 + 180  # next day
    assert usage_limit_pause('{"result": "ok"}') is None
