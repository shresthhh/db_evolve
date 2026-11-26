You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Template-copy aggregate state initialization for destructor-free layouts

**Hypothesis.** RowOperations::InitializeStates (src/common/row_operations/row_aggregate.cpp:8) calls aggr.function.GetStateInitCallback() indirectly once per state per aggregate. The E0045 implementer measured it at ~62-72ms CPU for q18's HAVING subquery (15M streamed runs). That makes it the third-largest per-group cost after the address fill (93ms) and UpdateStates (112ms). q18 is 180ms, the #3 template. The same function also initializes every new group in GroupedAggregateHashTable (FindOrCreateGroups), so every high-cardinality hash aggregate pays one indirect call per group per aggregate. For layouts with no destructor (!layout.HasDestructor()), the initialized state bytes are the same for every row. Initializing one template block and copying it with memcpy turns N*A indirect calls into A calls plus N fixed-size copies.

**Plan.** In src/common/row_operations/row_aggregate.cpp, RowOperations::InitializeStates: if !layout.HasDestructor() and count >= some small threshold (e.g. 4), use a template block. Allocate it once with GetAggrWidth() bytes; a thread_local or stack buffer is fine for widths <= 256 bytes, otherwise use the old path. Zero it. Run each aggregate's init callback once on template + (offsets[aggr_idx] - layout.GetAggrOffset()). Then, for each row i (through sel if set), memcpy(pointers[idx] + GetAggrOffset(), template, aggr_width). Specialize the copy loop for common widths (8/16/24/32/48/64 via a templated fixed-size memcpy) so it is not a libc call per row. Keep the old loop when there are destructors. Check that the aggregate offsets are contiguous from GetAggrOffset (tuple_data_layout.hpp:86-90); if any offset falls outside [aggr_offset, aggr_offset+aggr_width), fall back. Tests: the aggregate test suite (sum/avg/min/max/count/bit_and/arg_min/first, decimal and hugeint sums), q18 results, and GROUP BY with FILTER. Measure the q18 HAVING micro with .timer (baseline 136-143ms) and the full bench.

**Target files.** src/common/row_operations/row_aggregate.cpp

**Expected gain.** q18 -3..-6% (≈60ms CPU of the subquery's per-group cost). Small gains on other many-group hash aggregates (q03, q16, q09 partial aggregates, q18's main HT). Geomean ~-0.5..-1%.

**Generality.** Every grouped hash aggregate whose states have no destructor (sum/count/min/max/avg over numerics, which is most analytic GROUP BYs). Gains grow with the number of groups. List/string_agg/holistic aggregates keep the old path. Few-group aggregates do one extra template init per call, which is negligible.

**Risk.** Low. The one assumption is that the init callbacks write address-independent bytes. That holds for destructor-free states because they hold no owned pointers, and the gate excludes the rest. A contained, single-function diff.



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

This session is capped at about $15.00 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
