You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### FSST DFA filter: lane-refill interleaving + absorbing-state early exit

**Hypothesis.** After E0042, q13 (261ms, 2nd slowest) still spends 1.23s CPU in the orders scan (profile.md). Measured hot with dbe-tool sql: `count(*) WHERE o_comment NOT LIKE '%unusual%packages%'` takes 172ms wall / 1.35s user, and `NOT LIKE '%zq%'` (a 2-state DFA) takes 161ms. A full FSST decode of all 15M strings is cheaper: `WHERE o_comment <> 'abc'` takes 84ms and `sum(length(o_comment))` 88ms. So the code-level DFA is about 2x slower than decoding, even though it writes nothing. The cause is the loop in FSSTStorage::Filter (fsst.cpp:1114-1151). It groups 4 strings, runs the 4 interleaved chains only up to the SHORTEST length (`common`), then finishes each string's tail serially (`for k = common..lens[l]`). o_comment lengths vary widely (about 19-78 chars, so roughly 8-35 codes), so most codes run on a single dependent chain, `s = table[s + code]`, at about 6 cycles per code (L1 load latency plus the add). That is about 3ns/code, which matches 375M codes / 1.3s. Also, nothing exits early when the DFA reaches an absorbing state (the 'dead' state of a failed anchor, or 'done' when an unanchored-end pattern has matched). So a prefix pattern like 'forest%' or a contains of a common word still walks every code.

**Plan.** Only the inner loop and pattern init in src/storage/compression/fsst.cpp change. (1) In the FSST scan state's pattern initialisation (InitializePattern, around fsst.cpp:768-790, where pattern_table and pattern_accept are built), also compute per state whether it is absorbing: every one of the 256 code transitions, including the escape states, returns to the same state. FSSTPatternDFA::Build already creates explicit `done`/`dead` states (fsst.cpp:654-671), so this can simply be taken from there. Store it as a bit in pattern_accept (for example bit 1), or as a parallel vector indexed by s>>8. (2) Replace the 4-group loop (fsst.cpp:1114-1151) with a K-lane scheduler, K=8 (try 6/8/12). Each lane holds (cur ptr, end ptr, state, row). Each iteration advances every active lane by one code; this is the hot path with independent chains. When a lane reaches its end, or (checked every code or every few codes) enters an absorbing state, record accept for its row and refill the lane from the next candidate in sel. Rows that finish early must still land in new_sel in ascending order. Simplest: write a per-candidate pass/fail byte array indexed by candidate position i, then compact into new_sel in a final loop. Drain the remaining lanes at the end. Keep the escape-code handling exactly as it is now (escape states are ordinary table states, so it is unchanged). (3) Optional, measure separately: a speculative fast path for state 0 of unanchored patterns, `s = s ? table[s+c] : table0[c]`, which breaks the data dependency through branch prediction while the DFA sits in its start state. Micro A/B with .timer: NOT LIKE '%unusual%packages%', NOT LIKE '%zq%', LIKE '%unusual%packages%', contains(o_comment,'the'), and prefix-only LIKE 'ab%' on o_comment. Goal: below the 84ms decode baseline. Correctness: compare counts against the `o_comment||''` reference for the same pattern set the E0042 implementer used, including multi-%, anchors, NOT, escape-coded bytes, and candidate rows already narrowed by a previous filter.

**Target files.** src/storage/compression/fsst.cpp

**Expected gain.** q13: the scan accounts for about 170ms of a 261ms query. If the DFA reaches about 2x throughput (1.35s -> about 0.6s CPU), q13 drops to about 190-210ms (-20..-25%), roughly -1.5..-2% geomean. Templates without LIKE on FSST columns: 0.

**Generality.** Every LIKE/NOT LIKE/contains/prefix/suffix scan filter on an FSST VARCHAR column (comments, names, addresses). Early exit helps prefix-anchored patterns most (q20-style p_name LIKE 'forest%': dead after 1-2 codes) and contains on common words. Nothing changes for Dictionary/DictFSST/uncompressed columns. Worst case: very short strings, where lane-refill bookkeeping per string could cost more than it saves; o_comment and p_name are 20-80 chars.

**Risk.** Low-medium. One function plus an init-time flag, with no plan or plumbing changes. Correctness risk: rows reaching new_sel out of order, or lost lane state at the drain. Both are caught by count comparisons against the ||'' reference.



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
