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

### Batched per-vector FSST decode with a shared output bound

**Hypothesis.** The orders scan is 2.47s of ~3.5s CPU in q13, and measurements show FSST decode (~90ns per ~48B string) is most of it. Per row, FSSTScanState::DecompressString (fsst.cpp:556) calls FSSTPrimitives::DecompressValue (fsst.hpp:36). That does an arena Allocate(len*8), then duckdb_fsst_decompress with size=len*8, then FinalizeShrinkableBuffer/ShrinkHead. In duckdb_fsst_decompress (third_party/fsst/fsst.h:177) the fast 4-code loop only runs while posOut+32 <= size. Because size is only len*8, the last ~4 compressed bytes of every string fall into the branchy tail code, and strings shorter than 4 compressed bytes skip the fast loop completely. If the strings are decoded back to back into one per-vector allocation and size is passed as the remaining space in that allocation, the fast loop stays active up to each string's end. That also removes the per-row Allocate/ShrinkHead calls and the inline branches.

**Plan.** In FSSTStorage::StringScanPartial (src/storage/compression/fsst.cpp, the `else` branch around line 697, used when !all_values_inlined && decoder != nullptr) and in FSSTStorage::Select (line 724):
1. Sum the bit-unpacked compressed lengths bitunpack_buffer[offsets.scan_offset+i] over the rows to be decoded, giving total_bound = sum(len*8) + 32 slack.
2. Get one buffer with str_buffer.AllocateShrinkableBuffer(total_bound).
3. Keep a write position pos. For each row: if len==0, emit an empty string_t. Otherwise call n = duckdb_fsst_decompress(decoder, len, ptr, total_bound - pos, base+pos). If n <= string_t::INLINE_LENGTH, emit string_t(ptr, n), which copies the bytes inline, and do not advance pos. Otherwise emit string_t(base+pos, n) and advance pos += n.
4. At the end call allocator ShrinkHead(total_bound - pos), via a small new VectorStringBuffer helper next to FinalizeShrinkableBuffer in src/include/duckdb/common/types/vector_buffer.hpp. Before shrinking, construct every non-inlined string_t (the prefix is computed in the constructor) so that no later write touches the reclaimed tail. The decoder writes at most 8 bytes past each symbol, so the +32 slack covers it.
Keep the all_values_inlined path and the FSST-vector path unchanged. Check with SELECT count(*), sum(length(o_comment)), and also by comparing md5 of string_agg over a sample, that results match the old path.

**Target files.** src/storage/compression/fsst.cpp, src/include/duckdb/common/types/vector_buffer.hpp

**Expected gain.** q13: -4..-10%, from decode CPU (~1.4s of the scan) falling 10-25%.

**Generality.** Every scan or select of a non-inlined FSST VARCHAR column: string filters, string group keys, and string output. Memory use per vector is the same, because shrinking happens once. Nothing should get slower, except slightly larger transient arena use within one vector.

**Risk.** Low-medium. Memory-safety needs care: the bound must cover len*8 per string plus the 8-byte overwrite, with slack at the end; ShrinkHead must come after all writes. Inlined strings must be copied before pos is reused, which string_t(ptr,n) does.



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
