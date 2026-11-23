You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Per-key bloom filter for multi-key joins, revived for the post-E0008 q09 plan

**Hypothesis.** Since E0008 flipped the q09 plan at SF10, lineitem (59,986,045 rows, scan 3.60s CPU) is the PROBE side of a 2-key join (l_partkey = p_partkey AND l_suppkey = ps_suppkey). The BUILD side is part⋈partsupp: 435,892 rows, about 109k distinct partkeys out of 2M. That join costs 2.44s CPU and emits only 3,269,453 rows (5.4%). The lineitem scan gets only min/max dynamic filters, because JoinFilterPushdownInfo::CanUseBloomFilter (physical_hash_join.cpp:761-785) requires ht->conditions.size()==1. A bloom filter on the l_partkey key alone would cut the scan output from 60M to about 3.3M rows before the hash probe. E0005 built exactly this but was rejected because its premise was wrong for the OLD plan, where partsupp was the build side and lineitem was already filtered. In the current plan the premise holds, as verified by `dbe-tool profile q09.m0` this round. Its regressions (q19 +48%, q22 +21%) shrank to +9.9%/+4% on re-run, and q19 has only single-key joins, so they were most likely noise. Re-check them anyway.

**Plan.** Re-implement E0005's per-key bloom filter (see ledger E0005 for its design). JoinHashTable keeps one BloomFilter per equality condition index, initialised in AllocatePointerTable. Finalize fills it by gathering layout column cond_idx, running VectorOperations::Hash on it and calling InsertHashes. In CanUseBloomFilter, allow conditions.size()>1 when this condition is COMPARE_EQUAL, but keep build_side_has_filter and probe_larger_then_build. The deferred bloom-filter entries in FinalizeFilters (physical_hash_join.cpp:~814-900) carry the condition index, and PushBloomFilter uses that condition's BF, null semantics (NullValuesAreEqual(cond_idx)), key name and type. Keep wrapping it in SelectivityOptionalFilter so that a key that filters nothing (l_suppkey here) switches itself off at runtime. To bound build cost, build per-key BFs only for single-column equality conditions, at most 2 per join. Keep changes in .cpp files where possible; if a header must change (join_hashtable.hpp), build in the background. STEP 1: EXPLAIN ANALYZE q09.m0 and confirm the lineitem scan shows `l_partkey IN BF(...)` and emits far fewer than 60M rows. STEP 2: run the full bench, then re-run q18, q19 and q22 to rule out the E0005-era regressions.

**Target files.** src/execution/operator/join/physical_hash_join.cpp, src/execution/join_hashtable.cpp, src/include/duckdb/execution/join_hashtable.hpp

**Expected gain.** q09 (709ms, the slowest template): the 2.44s-CPU join probe drops to about 0.2s and the 3.6s lineitem scan sheds most of its downstream work. Expect q09 -25 to -40% and geomean -2 to -3%. Other templates: neutral unless they have a multi-key equality join with a filtered build side.

**Generality.** Any star or snowflake query that joins a big fact table to a filtered dimension on a composite key (partsupp-style bridge tables, (date, store) or (order, line) keys). Possible slowdowns: multi-key joins whose build side is large and unselective, which pay for building the BF and for about BF_CHECK_N chunks of probe hashing before SelectivityOptionalFilter turns it off.

**Risk.** Medium. NULL semantics per condition, condition-index bookkeeping after ReorderConditions (E0005's notes say indices match op.conditions == ht->conditions), and extra build-side hashing. E0005's code was reviewed as correct, which lowers the implementation risk.



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

This session is capped at about $9.21 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
