You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q13` (instances are in `.dbe/queries/`). The only timing that
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

### Fold compress(decompress(x)) pairs in compressed materialization

**Hypothesis.** In the q13 plan the RIGHT HASH_JOIN output (15.3M rows) goes into a PROJECTION `#0, __internal_decompress_integral_bigint(#1, 1)` that costs 0.18s CPU. The next PROJECTION immediately re-compresses the same column with `__internal_compress_integral_uinteger(#1, 1)` (0.01s) for the PERFECT_HASH_GROUP_BY. That is about 5% of the query's ~3.5s CPU spent turning a uinteger with offset 1 into a bigint and back. CompressedMaterialization creates the compress projection for the aggregate without checking whether its input is the output of a decompress projection that the CM pass for the join created just below it. Both expressions are pure, and compress(decompress(x, m), m) with the same compressed type and offset is the identity on x, so the pair can be removed.

**Plan.** In src/optimizer/compressed_materialization.cpp, CompressedMaterialization::CreateCompressProjection (or TryCompressChild, before the compress expression is built for a binding):
1. If child_op is a LogicalProjection, check the expression that produces the binding being compressed. If it is a BoundFunctionExpression for an __internal_decompress_integral_* function whose argument is a BoundColumnRef of type T_c with offset constant m, and the new compress expression is __internal_compress_integral_<T_c> with the same constant m (compare the bound function names and constant Values), apply the fold.
2. The fold: replace the child projection's expression at that index with the decompress argument (type T_c), and make the new compress projection emit a plain BoundColumnRef of type T_c for that column. Keep the stats from the compress expression, because the range is the same.
3. Only fold when the binding is referenced only by the new compress projection. That holds in the tree because the child projection's only parent is the operator being compressed. Assert it, and give up the fold if the decompressed binding is used anywhere else, for example in other expressions of the materializing op such as join conditions.
Strings (__internal_decompress_string / compress_string) can follow the same pattern but are optional; do integral first.
Check with EXPLAIN on q13: the decompress_integral_bigint projection between HASH_JOIN and PERFECT_HASH_GROUP_BY should be gone, or reduced to plain column refs.
Verify the function names in src/function/scalar/compressed_materialization/ (compress_integral.cpp) before matching on them.

**Target files.** src/optimizer/compressed_materialization.cpp

**Expected gain.** q13: about 0.19s of ~3.5s CPU, roughly -4..-6% wall.

**Generality.** Any plan where a compressed-materialization join feeds an aggregate, distinct or order on the same column, which is common in TPC-H style join→group-by queries. It only removes work and never adds any. Nothing should get slower, except in the rare case where the compressed value now flows into the aggregate through a narrower path, which is still the same data.

**Risk.** Low to medium. Getting the bindings or types wrong after replacing the expression could give wrong results or binder assertions. The fold must not fire when the offsets or compressed types differ, for example when the stats were updated between the two CM steps.



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
