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

### Reuse a per-scan-state string heap for FSST decoded strings

**Hypothesis.** In q13 the orders TABLE_SCAN costs 2.37s of the roughly 3.3s operator CPU. Round 5 microbenchmarks put o_comment decode at about 1.5s, about 100ns per string, which is far above the FSST decoder's speed of about 1 cycle per byte, and the overhead was never explained. In FSSTStorage::StringScanPartial<false> (src/storage/compression/fsst.cpp:696-701), every non-inlined string goes through FSSTPrimitives::DecompressValue (src/include/duckdb/common/fsst.hpp:36). That calls VectorStringBuffer::AllocateShrinkableBuffer(len*8) on the result vector's string heap. The scan vector's auxiliary is dropped on every chunk reset, so StringVector::GetStringBuffer (vector.cpp:2218) makes a fresh VectorStringBuffer whose ArenaAllocator starts at 2KB. ArenaAllocator::AllocateNewBlock (arena_allocator.cpp:63) doubles the block size, so each 2048-row vector of ~50-byte strings (about 100KB, plus len*8 headroom) does about 7 mallocs of 4KB to 256KB. It also wastes the leftover space of every old block. The larger blocks come from glibc malloc (no jemalloc is loaded), which serves them as fresh, often mmapped pages, so the scan page-faults and touches cold memory on every vector. Keeping one heap per scan state and reusing it when nobody else holds a reference fixes this: after warm-up, ArenaAllocator::Reset (arena_allocator.cpp:136) keeps the largest head block, so later vectors do zero mallocs into hot, already-mapped memory.

**Plan.** In src/storage/compression/fsst.cpp:
1) Add `buffer_ptr<VectorStringBuffer> cached_string_buffer;` to FSSTScanState.
2) In StringScanPartial, in the non-FSST-vector branch (line 696), before calling StringVector::GetStringBuffer, check three conditions: result_offset == 0, result has no auxiliary yet, and the vector type is FLAT. If they all hold:
   - If cached_string_buffer exists and cached_string_buffer.use_count() == 1, meaning no downstream vector or chunk still references it, reset its heap. Add a small `void Reset()` to StringHeap that calls allocator.Reset(), and expose it on VectorStringBuffer.
   - Otherwise create a new one, with make_buffer<VectorStringBuffer>() or with the result buffer's allocator, the same way GetStringBuffer does.
   - Then set result's auxiliary to cached_string_buffer. Use the existing setter if there is one (grep for SetAuxiliary in vector.hpp); otherwise use StringVector::AddBuffer semantics, or assign `result.auxiliary` through a friend or accessor.
   - Then proceed as before.
   Do not touch the case where result_offset > 0 (a scan continuing in the same vector across segments): keep the existing buffer there.
3) Optionally, reserve once per call to avoid the doubling chain on first use: sum the compressed lengths for this call, multiply by 8, and pre-grow the arena with a single Allocate and ShrinkHead, so there is one block per vector instead of seven.
Correctness: use_count()==1 guarantees nothing else holds the strings. Operators that keep strings (hash tables, sorts, Vector::Reference copies) either hold a reference to the auxiliary, which raises use_count so we don't reuse, or copy the strings into their own heaps. Check that DataChunk/Vector Reference and Slice share the auxiliary buffer_ptr rather than copying raw pointers. If any path copies string_t without the auxiliary, the reuse is unsafe there; check this with grep on `auxiliary` in vector.cpp.
Validate with:
- the q13 bench
- SELECT of the full o_comment column with ORDER BY/LIMIT, and string_agg over a group by
- a hash join with string payload, which must keep its strings after the scan advances
- CREATE TABLE AS SELECT of the column, compared by hash against the original
Compare all of these with checksums such as sum(hash(o_comment)) under the old and new builds.

**Target files.** src/storage/compression/fsst.cpp, src/include/duckdb/common/types/string_heap.hpp, src/common/types/string_heap.cpp, src/include/duckdb/common/types/vector_buffer.hpp

**Expected gain.** q13: if the allocation and page-fault overhead is a large part of the 1.5s decode, about -10 to -20% wall (scan is about 70% of CPU). At minimum it saves the 7 mallocs per vector, so likely at least -5%.

**Generality.** Every scan of an FSST-compressed VARCHAR column with non-inlined strings, which covers most string columns in persistent DuckDB databases: comments, names, addresses. It helps filters, projections and string aggregations. Nothing should get slower: when the buffer is still referenced downstream, it falls back to a fresh buffer exactly as today. The only cost is one cached heap per scan state, at most about 16MB if one vector held huge strings.

**Risk.** Medium. The main risk is a use-after-free if some downstream path keeps string_t pointers without holding the vector's auxiliary buffer_ptr. The use_count check covers every holder that keeps a reference. Hidden-query correctness checks will catch the rest. Memory held per scan thread is bounded by the largest vector's decoded size.



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
