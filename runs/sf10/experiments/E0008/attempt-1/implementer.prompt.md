You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Contains-filter scan selectivity to flip q09 build sides at SF10

**Hypothesis.** At the new data size (SF10), q09's two most expensive joins have their build side on the larger input. I verified this with `dbe-tool profile q09.m0`, where in HASH_JOIN the right child is the build side. (1) For l_orderkey=o_orderkey, the build is the full orders scan (15M rows) and the probe is lineitem⋈part (3.27M rows); the operator costs 2.97s CPU. (2) For p_partkey=ps_partkey AND l_suppkey=ps_suppkey, the build is partsupp⋈supplier (8M rows) and the probe is the same 3.27M stream; it costs 2.82s CPU. Together these are about 5.8s of q09's roughly 10s CPU. Two things cause this. The part scan filter contains(p_name,'ghost') gets the flat DEFAULT_SELECTIVITY of 0.2, so part is estimated at 400k rows while the actual count is 109k. That makes lineitem⋈part about 12M estimated versus 3.27M actual, which is comparable to orders (15M) and larger than partsupp (8M), so the optimizer builds on orders and partsupp. With selectivity 0.04 the estimate becomes about 2.4M. That is far below both 15M and 8M, so the build-probe optimizer should put the 3.27M side on the build side of both joins. orders (15M) and partsupp (8M) would then become probes and get bloom/min-max filters. E0002 tested exactly this code at SF1 and saw no plan change, because at SF1 orders was already the probe side. The data size has changed the situation since then.

**Plan.** Re-implement E0002's minimal change, restricted to contains(). In src/optimizer/join_order/relation_statistics_helper.cpp, add a file-local static `IsContainsFilter(const TableFilter&)`. It returns true for an ExpressionFilter whose expression is a BoundFunctionExpression named "contains" with a non-empty VARCHAR constant argument. It also recurses into ConjunctionAndFilter children. Look up the actual filter classes in src/planner/filter/ (expression_filter, conjunction_filter) and handle OPTIONAL_FILTER the same way as the surrounding code. Do NOT match prefix(), suffix(), LIKE with a single leading %, NOT, or OR. Suffix patterns like '%BRASS' are genuinely about 0.2 selective. In ExtractGetStats (around line 146-151), when there is no equality filter and a non-optional filter is a contains filter, use 0.2*0.2 instead of DEFAULT_SELECTIVITY. Keep the change out of headers, i.e. file-local constexpr. STEP 1, before the bench: build in the background, then run EXPLAIN ANALYZE on q09.m0 with `dbe-tool sql`. Confirm that the l_orderkey join now has the lineitem/part side as the build (right child) and orders as the probe, and the same for partsupp. If the plan does not flip, look at src/optimizer/build_probe_side_optimizer.cpp to see why (width or cost terms), report that, and stop. STEP 2: run the full bench.

**Target files.** src/optimizer/join_order/relation_statistics_helper.cpp

**Expected gain.** q09 (24% of total time, 1.2s): if both joins flip, the hash table builds go from 15M+8M rows down to 2×3.27M, and orders and partsupp get bloom-filtered probes. Expected 30-50% faster on q09. Other templates are unchanged unless they have a contains filter.

**Generality.** Any query with a '%word%' LIKE or contains() filter on a dimension table that is joined to a fact table. Substring matches are almost always much more selective than 20%. It could get slower when a contains literal is very unselective, such as a single common character, which could flip a join the wrong way. A fallback option is to apply it only for literals of 3 or more characters.

**Risk.** Low-medium. The diff only changes estimates in one file. The main risk is plan changes in hidden templates that use contains filters. E0002 already showed that this code builds and moves the estimates as intended.



## How your change will be judged

After you finish, an automated harness that you cannot influence does the following, in order.
Failing any step sends the change back to you or retires it.

1. Path policy. Only files under `src/`, `extension/parquet/`, `extension/core_functions/` may change; `test/`, `benchmark/`, `tools/`, `scripts/`, `extension/tpch/`, `extension/tpcds/`, `.github/` are off limits.
2. Static audit. Added lines must not mention the workload: no table or column names, no query
   literals, no benchmark names.
3. Build. Release build of the whole engine.
4. Correctness. Results must equal the original engine's on the visible queries, on new parameter
   values for those queries, on query templates you have never seen, on a second dataset of a
   different size, and on a suite of generic SQL over an unrelated schema.
5. Review. An independent reviewer reads your diff looking for benchmark-specific shortcuts and
   correctness holes.
6. Timing. Interleaved runs against the current best. The bar was fixed in advance:
   at least one visible template at least 5% faster (more for templates whose timings are noisy); no template, visible or hidden, slower by more than 5% (again more for noisy ones); and the visible geomean not slower. A change that makes one kind of query clearly faster and nothing slower is accepted.

So the only changes that survive are ones that make the engine faster for a whole class of
queries. Read `.dbe/knowledge/rules.md` before you start; it is short.

## Working

- `.dbe/knowledge/` has a codebase map, a profiling guide and an optimization playbook.
  `.dbe/queries/` has the visible queries. `.dbe/profile.md` shows where time goes today.
- Shell access is limited to one command, `/home/shresth/dev/db_evolve/bin/dbe-tool`. Anything else (python, grep, find, cd, pipes,
  git) is blocked, so do not spend turns on it: search code with the Grep and Glob tools, read with
  Read, edit with Edit. Never run anything in the background: this is a non-interactive session
  and it ends as soon as you stop to wait.
  - `/home/shresth/dev/db_evolve/bin/dbe-tool build` builds your working tree incrementally and prints compiler errors. A rebuild
    after a header change can take 10 to 15 minutes. The command returns after about two minutes
    with `BUILD RUNNING`; call it again until it prints `BUILD OK` or `BUILD FAILED`.
  - `/home/shresth/dev/db_evolve/bin/dbe-tool bench [template ...]` checks results and times the visible queries, your build
    against the current best. Without arguments it runs all visible templates.
  - `/home/shresth/dev/db_evolve/bin/dbe-tool profile <instance>` prints the query plan with per-operator timings from your build
    (instance ids look like `q06.m0`; `/home/shresth/dev/db_evolve/bin/dbe-tool queries` lists them).
  - `/home/shresth/dev/db_evolve/bin/dbe-tool sql "<statement>"` runs one statement on your build against the benchmark database
    (read-only).
- Measure before and after. If the profile does not show the cost you expected, say so and stop
  rather than shipping a change with no effect: finish with status `abandon` and explain what you
  found. That is a useful result, and it is recorded.
- Keep the diff as small as the idea allows and follow the surrounding code's conventions. New
  source files must be added to the directory's `CMakeLists.txt`.
- Think about inputs the visible queries never exercise: NULLs, empty inputs, other types, values
  at the limits of what your fast path handles, out-of-memory spilling, parallel execution. The
  hidden checks do.
- Do not commit or revert; the harness commits your working tree when you finish, or saves it for
  the record and resets the tree if you abandon.
- Prefer changes to `.cpp` files over headers where the idea allows: they rebuild in a minute or
  two instead of ten or more.

## When you finish

Return `status` (`ready` if the tree builds and you want it judged, `abandon` otherwise),
`summary` (what you changed and the before/after numbers you measured), `generality` (the class of
queries this helps and the cases where it does not apply), and `notes` (anything the planner
should remember: dead ends, surprises, follow-up ideas).

## Budget

This session is capped at about $10.57 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
