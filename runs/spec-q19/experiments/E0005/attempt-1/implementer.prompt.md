You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q19` (instances are in `.dbe/queries/`). The only timing that
counts is on these visible templates. Other kinds of queries may
get slower, but every query must still return correct results, and it is checked on many query
shapes you cannot see.

The code must stay general in what it refers to. Specialise to the *shape* of the query (its
operators, join structure, kinds of predicates and aggregates, data types, cardinalities), never to
names: no table or column names, no literal values from the queries, no knowledge of this dataset
(row counts, value distributions), and no caching of results across executions. A condition that
only this shape of query meets is fine here; a condition that names this query is not. Parameter
values change between runs and the data size changes, so anything tied to either will fail.


## The issue

### Cost-aware initial scan filter order: run Bloom/dynamic join filters after cheap constant predicates

**Hypothesis.** Most of q19's time is the lineitem TABLE_SCAN (4.05-6.18s cumulative, ~85%). Standalone A/Bs in one dbe-tool session show the Bloom-filter join filter on l_partkey is the most expensive filter per row: BF-only scan 2.44s cum (349ms wall), shipinstruct-eq + quantity-OR without BF 1.57s (204ms), all three together 2.09s (286ms). Adding cheap selective predicates made the scan cheaper because less hashing was done. ExpressionHeuristics::Cost(const TableFilter&) (src/optimizer/expression_heuristics.cpp:225) gives OPTIONAL_FILTER/DYNAMIC_FILTER a cost of 0, so the l_partkey filter AND(opt>=, opt<=, opt BF) costs 5. That ties with the VARCHAR equality (ExpressionCost(VARCHAR,1)=5). EXPRESSION_FILTER falls to default 1000. The TableFilterSet map is keyed by scan column index, and the l_partkey column comes before l_shipinstruct. GetInitialOrder's sort on 4 elements is an insertion sort and keeps that order, so the initial permutation is [shipmode(always-true), partkey-BF, shipinstruct, quantity]. That means the BF hashes and probes all ~60M rows instead of the ~25% that pass shipinstruct. AdaptiveFilter (src/execution/adaptive_filter.cpp) can only fix this with random swaps judged on noisy 10-vector wall timings. One of the 3 swap slots involves the always-true shipmode filter, so those swaps are no-ops. Giving the BF a realistic, higher cost, and giving SelectivityOptionalFilter its child's cost, puts the BF after cheap comparisons from the first vector.

**Plan.** In src/optimizer/expression_heuristics.cpp, ExpressionHeuristics::Cost(const TableFilter &filter):
(1) case BLOOM_FILTER: return a hash-plus-probe cost, e.g. 50. That is above simple constant comparisons (1-5) and below generic expressions.
(2) case OPTIONAL_FILTER: if dynamic_cast<const SelectivityOptionalFilter *>(&filter) succeeds (include duckdb/planner/filter/selectivity_optional_filter.hpp), return Cost(*child_filter), because it really filters. A plain OptionalFilter stays 0, since it is skipped anyway.
(3) Optional, only if (1)+(2) alone do not reorder q19: EXPRESSION_FILTER returns Cost(*expr_filter.expr) via the existing Expression cost instead of 1000. Then a numeric OR-of-ranges (~104) is no longer treated as maximally expensive.
Keep DYNAMIC_FILTER at 0. Change nothing in AdaptiveFilter.
Verify with an A/B on the same build (temporarily switch the new branch on and off, or compare against the current best with bench run twice): the q19 lineitem scan cumulative time in `dbe-tool profile q19.m0`, then bench q19. Also sanity-check `SELECT sum(l_extendedprice) FROM lineitem WHERE l_partkey IN (SELECT p_partkey FROM part WHERE p_size<=5 AND p_brand='Brand#45')` (BF-only), so a scan where the BF is the only filter is unaffected.

**Target files.** src/optimizer/expression_heuristics.cpp

**Expected gain.** q19: if the BF currently runs first on all rows, moving it after the 25%-selective string equality should cut BF hash/probe work ~4x. Estimate -10..-25% q19. It is 0% if AdaptiveFilter had already converged to that order (then retire, and note that ordering is not the bottleneck).

**Generality.** Any scan probing a hash-join build where the scan also has cheap local constant predicates: star joins, TPC-H Q3/Q5/Q9/Q10/Q12/Q19-like shapes. This affects only the initial filter permutation, and AdaptiveFilter can still swap at runtime. It could get slightly slower when local predicates are unselective and the BF is very selective, but SelectivityOptionalFilter and adaptive swaps limit that. Results cannot change, because filter order does not affect correctness.

**Risk.** Low. It only reorders conjunctive table filters, and all of them are evaluated anyway. dynamic_cast on TableFilter is polymorphic and safe. The main risk is no measurable gain within bench noise (~5-10%).



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
   at least one visible template at least 5% faster (more if its timings are noisy), no visible template slower beyond its noise, and the visible geomean not slower. Templates you cannot see are not timed in this run; they only have to stay correct.

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

This session is capped at about $15.00 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
