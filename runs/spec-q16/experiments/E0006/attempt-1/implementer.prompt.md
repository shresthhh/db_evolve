You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q16` (instances are in `.dbe/queries/`). The only timing that
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

### Evaluate small integral constant IN lists inline instead of a MARK join

**Hypothesis.** In q16 the part scan emits 1,856,009 rows (0.10s CPU). The pushed `p_size IN (8 consts)` is only an OptionalFilter, used for zonemap pruning (filter_combiner.cpp:580-585). InClauseRewriter::VisitReplace (in_clause_rewriter.cpp:60) turns IN lists with >=6 constants into a MARK join against a COLUMN_DATA_SCAN, followed by a FILTER on the mark column. So every one of the 1.86M part rows is hashed, probed and marked before 84% of them are dropped. All of this happens in the join build pipeline, which has to finish before the partsupp probe pipeline starts, so it sits on the critical path. For a short list of integer constants, a vectorized membership test (a few compares per row, or a bitmap) is much cheaper than a hash-join probe. It also lets the FILTER put the cheap integer predicate ahead of the string predicates (brand <>, NOT LIKE).

**Plan.** 1) src/optimizer/in_clause_rewriter.cpp InClauseRewriter::VisitReplace: before the mark-join path (after the `< 6` check), return nullptr (keep the BoundOperatorExpression COMPARE_IN/NOT_IN unchanged) when all of these hold: children[0]->return_type is an integral physical type of at most 64 bits (INT8..INT64, UINT8..UINT64; no HUGEINT, no DECIMAL needed), every child from 1 on is a non-NULL BoundConstantExpression, and children.size()-1 <= 64. 2) src/execution/expression_executor/execute_operator.cpp: add a fast path to the COMPARE_IN/NOT_IN branch (line 23) for the same condition. Cast the constants to int64 (or to the physical type), then evaluate the left vector with UnifiedVectorFormat. If max-min < 4096, test with a bitmap (vector<bool>/bitset built per call, or cached in ExpressionState if simple); otherwise use a sorted array with binary search. Write a BOOLEAN result that is NULL where the left side is NULL and true/false (inverted for NOT IN) otherwise. Keep the existing generic loop for everything else. Make sure the Select path (filter) goes through this Execute path or add a Select specialization. Check that the FILTER over part.p_size now evaluates IN directly and that the MARK join is gone from the q16 EXPLAIN.

**Target files.** src/optimizer/in_clause_rewriter.cpp, src/execution/expression_executor/execute_operator.cpp

**Expected gain.** q16 3-6% wall: removes a 1.86M-row mark-join probe and its hash from the serial build-side pipeline (scan+filter+mark ~0.13s+ CPU).

**Generality.** Any query with a filter or projection of the form int_col [NOT] IN (6..64 integer constants), which is very common in TPC-H/DS-style workloads (sizes, years, ids). Lists with more than 64 values, non-integral types and non-constant lists keep the mark join. Possible slowdown: a 64-value list with a wide range uses binary search, which is still cheaper than a hash probe.

**Risk.** Low-medium. NULL semantics: left NULL gives NULL. Constants are non-NULL by the gate, so NOT IN has no NULL-in-list edge case. Integer constants must already be cast to the left type (the binder does this); assert or bail out if the types differ.



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
