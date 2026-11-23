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

### SWAR first+last-byte candidate scan in FindStrInStr for short haystacks

**Hypothesis.** In q13 the orders TABLE_SCAN with the NOT LIKE '%w1%w2%' filter is 2.40s of about 3.35s total operator CPU. Microbenchmarks at 8 threads, as scan operator CPU on orders: two integer columns only 0.41s; plus decoding o_comment with length(o_comment)>45 1.92s; NOT contains(o_comment,'qqqqqqq') with a rare first byte 2.23s; NOT contains 'eeeeeee' with a common first byte 2.44s; the actual q13 NOT LIKE 2.36s. At 1 thread the same scan is 2.09s, so the cost is per-row compute, not bandwidth. Matching therefore costs about 0.3-0.5s CPU on top of decoding. Even with a first byte that never occurs it costs about 0.3s, which is the fixed cost per string of calling memchr. FindStrInStr (src/function/scalar/string/contains.cpp:76) calls memchr for needle[0], then Contains<> calls memchr again for every candidate position. On short strings (about 50 bytes) with common first bytes, that means several libc calls per string, each with setup and branch overhead. A branch-light candidate filter would mostly remove the matcher cost: compare 8 (SWAR) or 16 (SSE2) positions at once against needle[0] at offset i and against needle[n-1] at offset i+n-1, AND the two masks, and verify only the surviving candidates with memcmp (Muła's generic SIMD strstr).

**Plan.** In src/function/scalar/string/contains.cpp, add a fast path inside FindStrInStr(const unsigned char*, idx_t, const unsigned char*, idx_t), used when needle_size >= 2 and haystack_size >= needle_size - 1 + 8. Set first = broadcast(needle[0]) and last = broadcast(needle[n-1]). For i in steps of 8 while i + n - 1 + 8 <= haystack_size: A = Load<uint64_t>(h+i) ^ first; B = Load<uint64_t>(h+i+n-1) ^ last; take the zero-byte mask of (A|B) with the classic haszero ((x - 0x0101..) & ~x & 0x8080..). It can give false positives only above a true zero byte, and memcmp catches those. For each set bit, from low to high: pos = i + ctz(mask)/8; if memcmp(h+pos+1, needle+1, n-2) == 0, return pos (n==2 needs no memcmp). Positions must be visited in ascending order so the leftmost match is returned, because LikeMatcher::Match depends on the leftmost offset. After the loop, hand the remaining tail [i, end) to the existing memchr/Contains<> code with base_offset=i, or to a plain scalar loop. Every load must stay inside [haystack, haystack+haystack_size), with no over-read. Optionally use SSE2 for 16-byte blocks under #ifdef __SSE2__ with _mm_movemask_epi8, keeping the SWAR path as the portable fallback. Little-endian only for ctz bit order: on big-endian, use the existing path (#if on __BYTE_ORDER__). Keep the semantics identical: return the offset of the first match or INVALID_INDEX. Test against the old implementation on random strings, needles of length 1-20, matches at the start, at the end, overlapping and repeated-prefix cases, plus contains/strpos/LIKE/ILIKE queries.

**Target files.** src/function/scalar/string/contains.cpp

**Expected gain.** q13: about 0.2-0.35s of the roughly 0.45s matcher CPU (of 3.35s total), so -5 to -10% wall. Any LIKE '%x%', contains, strpos or instr filter on string columns gets faster.

**Generality.** Every substring search: LIKE with % segments, contains(), position/strpos/instr, NOT LIKE, ILIKE after lowercasing if it routes here. No query shape should get slower, except possibly very long haystacks with a rare first byte, where glibc's AVX2 memchr would beat 8-byte SWAR. The SSE2 variant or a fallback to memchr when haystack_size > 256 removes that case.

**Risk.** Low to medium. It is a pure function with exact semantics, but over-reads and returning the leftmost match must be right. It is easy to unit-test against the old code.



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
