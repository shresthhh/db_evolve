You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Join filters (min-max + bloom) for RIGHT_SEMI/RIGHT_ANTI probes and equality for deliminated EXISTS conditions

**Hypothesis.** After E0011, q04 runs as one HASH_JOIN RIGHT_SEMI: probe = lineitem (37.9M rows after l_commitdate<l_receiptdate, from a 60M scan), build = filtered orders (574k rows). The join takes 0.89s CPU and the lineitem scan gets NO dynamic or bloom filter. There are two blockers, both verified in code. (1) JoinFilterPushdownOptimizer::GenerateJoinFilters (src/optimizer/join_filter_pushdown_optimizer.cpp:207-219) returns early for RIGHT_SEMI and RIGHT_ANTI. That is overly conservative: in both types the output comes from the build side, so a probe row whose key is not in the build can never affect the result. Only left ANTI, MARK, SINGLE, LEFT and OUTER really need every probe row. (2) The deliminated delim join keeps its condition as `o_orderkey IS NOT DISTINCT FROM o_orderkey`, and GenerateJoinFilters skips COMPARE_NOT_DISTINCT_FROM (line 237). In Deliminator::RemoveJoinWithDelimGet (deliminator.cpp:245-253), each removed plain =/<> correlation condition already adds an IS NOT NULL filter on the subquery-side column. With the RHS key known non-NULL, NOT DISTINCT FROM is equivalent to = for SEMI, ANTI and INNER (a NULL LHS key matches nothing either way). Manual test: rewriting q04 as an explicit SEMI JOIN with = gives the same RIGHT_SEMI plan, still unfiltered because of blocker (1), and 182-210ms vs 214ms. So blocker (2) alone gains little, and the main gain needs (1). The build covers about 3 months of 7 years of orders, so a bloom filter on l_orderkey should cut the probe rows about 15-25x.

**Plan.** A. src/optimizer/join_filter_pushdown_optimizer.cpp GenerateJoinFilters: remove RIGHT_SEMI and RIGHT_ANTI from the early-return list. Keep MARK, SINGLE, LEFT, OUTER and ANTI, and update the comment to say why the right-variants are safe. Leave compute_aggregates_anyway INNER-only, so the perfect-HT behaviour does not change. Check physical_hash_join.cpp (Sink line 339, Finalize 1006-1025) and the bloom filter code (CanUseBloomFilter/PushBloomFilter) for join-type assumptions. B. src/optimizer/deliminator.cpp Deliminator::Optimize: when the candidate is fully removed (the type is changed to LOGICAL_COMPARISON_JOIN at line 109) and every removed correlation condition was a plain COMPARE_EQUAL (so an IS NOT NULL filter was added for each delim column), rewrite the delim_join conditions from COMPARE_NOT_DISTINCT_FROM to COMPARE_EQUAL. Do this only for join_type SEMI, ANTI or INNER, and track it with a local flag. Do not do it if any removed condition was NOT DISTINCT FROM or DISTINCT FROM. Use file-local statics only, with no header changes. Validate with EXPLAIN ANALYZE of q04.m0: the lineitem scan should show a dynamic/bloom filter on l_orderkey and far fewer than 37.9M rows into the join. Also check q22 and q18, where the IN subquery may be RIGHT_SEMI. Correctness: NOT EXISTS and EXISTS with NULL keys on both sides, a RIGHT_ANTI case where the build has keys absent from the probe, and an IN subquery, all checked against unoptimized results (SET disabled_optimizers='join_filter_pushdown').

**Target files.** src/optimizer/join_filter_pushdown_optimizer.cpp, src/optimizer/deliminator.cpp

**Expected gain.** q04 207ms -> roughly 120-150ms (the join is 0.89s CPU, and most of the lineitem scan/filter feeding it is avoidable). q22 and q18 possibly, if their semi/anti joins are right-flipped. Geomean about 2-4%. Hidden EXISTS, NOT EXISTS and IN templates (TPC-H q20/q21-like) likely benefit.

**Generality.** Any EXISTS, IN or NOT EXISTS subquery, or explicit semi/anti join, where the optimizer puts the small outer side on the build (RIGHT_SEMI/RIGHT_ANTI) and the big table on the probe. That is a very common analytical pattern. Possible slowdowns: unselective filters add bloom/min-max probing cost on scans, but the existing selectivity-based runtime disable mitigates that, the same as for INNER joins.

**Risk.** Medium-low. Correctness risk is in part B's NULL semantics (limited to fully-deliminated joins whose correlation conditions were all plain equality with IS NOT NULL added) and in any hidden join-type assumption in the physical filter code. The diff is small and in two .cpp files.



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

This session is capped at about $4.85 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
