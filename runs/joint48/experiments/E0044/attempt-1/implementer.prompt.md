You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### FSST DFA filter: SIMD skip of codes that keep an unanchored DFA in state 0

**Hypothesis.** The q13 orders scan (o_comment NOT LIKE '%unusual%packages%', 15M rows) is still the largest piece of q13 (237ms, 12% of the total). E0043's probes split the count micro query (~160ms) as follows: a floor of ~75ms without the DFA walk, ~25ms for touching the string bytes, and ~60ms for the per-code dependent table walk in FSSTStorage::Filter (fsst.cpp:1115-1151). Adding ILP (8 lanes, rounds, length-sorted groups) did not help, so making each lookup faster is a dead end. The remaining lever is doing fewer lookups. For an unanchored pattern, the DFA sits in state 0 for almost every code. Only codes whose symbol bytes move state 0 to a non-zero state (pattern_table[0 + c] != 0: symbols ending in a prefix of the first literal, plus FSST_ESC=255) can start progress. A 16-code SIMD membership test on a 256-bit 'leaves state 0' set finds the next such code, so the scalar walk runs only from there until it returns to state 0. For rare literals that cuts the scalar lookups by about 5-10x. The walk's ~60ms should drop to ~10-20ms, so q13 falls ~15-20%.

**Plan.** In src/storage/compression/fsst.cpp: (1) In FSSTScanState::InitializePattern (~:771), after building pattern_table, compute a 256-bit set leave0[c] = (pattern_table[c] != 0) for c in 0..255. FSST_ESC always leaves, because it maps to a pending state. Also build pshufb nibble tables: for each low nibble, an 8-bit mask over (hi & 7), with separate tables for hi < 8 and hi >= 8. Set a flag skip_ok = has_pattern && !anchored_start && popcount(leave0) <= 128. Anchored-start patterns already reach a dead state quickly, so leave them alone. To see anchoring, either expose it from FSSTPatternDFA::Build/TryCreate (:551/:622) or derive it as 'state 0 is not reachable from state 0 via some code'. Simplest: skip_ok only if pattern_table[0 + c] == 0 for most c. (2) In FSSTStorage::Filter (:1081), when skip_ok, replace the 4-lane loop with a per-string loop: k = 0; s = 0; loop { if s == 0: find the next k' >= k with leave0[str[k']] using a 16-byte SIMD block test (load 16 bytes, mask off the bits past len, take the first set bit); if none is found, break with s = 0; otherwise k = k'. Then run scalar s = table[s + str[k]]; k++ while s != 0 && k < len }. Accept with accept[s >> 8] as today. The pending-escape states are >= 256*pattern_states and so are non-zero, so the scalar path consumes the escape byte correctly. Reading past the string end: compressed strings sit back to back in the segment dictionary, but the 16-byte load must not cross the end of the block buffer (scan_state.handle.Ptr() + segment block size). Near the end, use a scalar loop over leave0 instead. (3) SIMD portability: use SSSE3 _mm_shuffle_epi8 nibble lookup inside a function with __attribute__((target("ssse3"))) and __builtin_cpu_supports("ssse3") checked once, or #if defined(__SSSE3__). Otherwise use a scalar fallback that tests a 256-byte leave0 flag array. Those flag lookups are independent loads, not a dependent chain, so the fallback is still a win. Check how E0032 / column_segment.cpp included SSE intrinsics and follow the same convention. (4) Test LIKE, NOT LIKE and contains with infix, multi-%, suffix-anchored and prefix-anchored patterns (the prefix-anchored ones keep the old path). Include a pattern whose first byte is common ('%e%'), a pattern matching inside an escape-coded byte, and strings shorter than 16 codes at the block end. Compare counts with the o_comment||'' reference (which disables pushdown). Micro A/B with .timer: count(*) WHERE o_comment NOT LIKE '%unusual%packages%' (r11 baseline 172ms), NOT LIKE '%zq%' (161ms), contains 'the' (147ms; must not regress).

**Target files.** src/storage/compression/fsst.cpp

**Expected gain.** q13 -10..-20% (scan walk ~60ms of wall time → ~15ms); geomean ~-1..-1.5%. Hidden templates: any LIKE '%lit%' / contains filter on an FSST comment or name column (q16-style s_comment, p_name LIKE '%green%' shapes).

**Generality.** Every unanchored LIKE/contains/NOT LIKE scan filter on an FSST-compressed VARCHAR column. It is an exact rewrite of the same DFA walk, so results are unchanged. It can be slower when the first literal byte is very common (e.g. '%e%', where most codes leave state 0): the popcount gate plus a per-vector fallback would bound that cost. A simple per-vector option: if the scalar step count exceeds about half the codes, switch to the old loop for the rest of the segment.

**Risk.** Medium-low. One file, and the DFA semantics are unchanged. The main bug risks are over-reading past the block buffer and mishandling escape-pending states. The 16-byte tail guard and the reference tests cover both. Performance risk: q13's noise is ~14%, so the change needs to clear that; rerun q13 alone if the result is borderline.



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
