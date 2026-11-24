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

### Vector-at-once substring prefilter for LIKE/contains scan filters on FSST columns

**Hypothesis.** After E0001 and E0003, the orders TABLE_SCAN with the pushed `o_comment NOT LIKE '%a%b%'` ExpressionFilter takes 2.54s of about 3.6s total CPU in q13 (profile.md). Standalone timings split that cost: `sum(length(o_comment))` (FSST decode only) runs in about 106 ms. The same scan with `NOT LIKE '%x%y%'` takes 236 ms, `contains(col,'x')` 215 ms, and a suffix-only `LIKE '%zzzz'` 110 ms. So about half the scan is the per-row substring search: LikeMatcher::Match (like.cpp:231) calls FindStrInStr for each row (contains.cpp:76), which is a memchr on the needle's first byte followed by a Load/compare loop. With 48-byte strings and a common first letter, that means several memchr calls and branch mispredictions per row across 15M rows. FSST has no compression->filter, so StandardColumnData::Filter falls back to ColumnData::Filter (column_data.cpp:348). That function scans an FSST_VECTOR, flattens it with ToUnifiedFormat (each string decoded separately into the heap), then evaluates the expression row by row through ColumnSegment::FilterSelection's EXPRESSION_FILTER case (column_segment.cpp:563). If the vector's strings are decoded into one contiguous buffer and the required literal is searched once over the whole buffer (about 100KB per vector), the search costs a few ns per row instead of tens. Rows with no occurrence get their LIKE result without any per-row work.

**Plan.** In ColumnData::Filter (src/storage/table/column_data.cpp:348), before ToUnifiedFormat, add a fast path. It applies when: (a) after Scan the result is VectorType::FSST_VECTOR; (b) the filter is an ExpressionFilter whose expr is exactly a BoundFunctionExpression `~~` (LIKE), `!~~` (NOT LIKE) or `contains`, with child 0 a BoundReferenceExpression and child 1 a constant VARCHAR without collation, optionally wrapped once in NOT. For LIKE the pattern must contain no '_' and no escape, and must have at least one literal segment of at least 2 bytes between % signs or at the start/end (reuse the segment-splitting logic of LikeMatcher::CreateLikeMatcher in like.cpp:290; copy it or expose a small static helper that returns the longest literal segment). Then: 1) Decode all scan_count strings into ONE contiguous buffer allocated from the result vector's string heap, so its lifetime matches the vector. Get the decoder from FSSTVector::GetDecoder and the compressed string_t values from FSSTVector::GetCompressedData<string_t>. Bound the buffer size by the compressed sizes × 8, the FSST max expansion, or by the sum of the decoded sizes. Decode each row with duckdb_fsst_decompress, the same call FSSTPrimitives::DecompressValue makes, into a running offset, record offsets[i], and write result_data[i] = string_t(ptr, len) so the result becomes a valid FLAT_VECTOR. Keep the FSST validity: NULL rows get an empty string and stay invalid. 2) Search for the needle across the whole buffer once. Use a SIMD candidate filter on the needle's first and last bytes (SSE2 16B, or AVX2 if available; E0002's code has an overlapping-tail version), memcmp the middle, and do not let a candidate start in the last needle_size-1 bytes of the buffer. Map each hit to its row by advancing a monotone row cursor over offsets, and accept it only if hit+needle_size <= row_end, so hits spanning two rows are rejected. After the first hit in a row, jump to that row's end. 3) Rows with no hit and a valid value: for LIKE or contains the result is false; for NOT LIKE it is true. Rows with a hit are candidates: evaluate the original expression on them only, by slicing the flat result with a candidate SelectionVector and reusing the existing EXPRESSION_FILTER logic (the ExpressionFilterState executor in ColumnSegment::FilterSelection), or by calling FilterSelection with an initial sel holding only the candidates. Merge the decided rows and the approved candidates into `sel` in ascending order and set s_count. NULL rows are never approved. Respect an incoming sel/approved count by only considering rows already in sel. In every other case, including flat vectors, non-matching expressions and AND/OR filters, keep the existing path unchanged. Optional, only if easy: when the compressed strings of consecutive rows are adjacent in the dictionary (stored in reverse order), decode them with a single duckdb_fsst_decompress call.

**Target files.** src/storage/table/column_data.cpp, src/function/scalar/string/like.cpp, src/function/scalar/string/contains.cpp, src/include/duckdb/function/scalar/string_common.hpp

**Expected gain.** q13: scan CPU 2.54s → ~1.4s. Wall about -12..-20% (511 → ~420-450 ms).

**Generality.** Any substring-type filter pushed into a table scan over an FSST-compressed VARCHAR column: LIKE '%x%', NOT LIKE '%x%y%', contains(), and multi-segment LIKE. Common in analytical workloads such as TPC-H q9 (part names), q13 and q16 (comments). Prefix/suffix-only LIKE also gets cheaper decoding. Nothing should get slower: patterns that don't qualify, flat vectors and other compressions keep the old path. The worst case is a needle present in almost every row, where all rows fall through to the old per-row evaluation after an extra buffer search (≤ ~10% overhead on that filter).

**Risk.** Medium. Risks are correctness at row boundaries (cross-row hits, empty strings, NULLs, strings ≤12 bytes that must be inlined in string_t), buffer sizing (strings over the block limit), and keeping sel order. The fast path must be verified against the old path with SQL: compare `col LIKE p` against `(col || '') LIKE p`, which disables pushdown, over a grid of patterns, including the needle at the start and end of a row, a needle spanning two adjacent rows, NOT LIKE with NULLs, and contains(). Also check with EXPLAIN that the filter is still pushed into the scan.



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
