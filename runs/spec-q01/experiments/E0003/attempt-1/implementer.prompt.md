You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q01` (instances are in `.dbe/queries/`). The only timing that
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

### Perfect HT: replicate group states (K=4) to break same-state dependency chains

**Hypothesis.** PERFECT_HASH_GROUP_BY is 1.50s CPU for 58.8M rows (~25ns/row, 8 aggregates) in profile.md. q01 has 4 groups with skew (N,O ~49%, A,F/R,F ~25% each). In RowOperations::UpdateStates -> UnaryScatter, every row of a group does a read-modify-write on the same state address, so all rows of one group form a serial chain through store-to-load forwarding (~4-6 cycles per link, longer for avg's hugeint add with carry). Out-of-order execution only overlaps the different groups, so throughput is limited by the largest group: about 0.49 x 5 cycles per row per aggregate. E0001 changed the loop structure, partitioning rows by group, and that overhead made it slower. This change keeps the existing vectorised scatter unchanged and only changes the addresses: row i goes to replica (i & 3) of its group. That splits each chain into 4 independent chains. Measured with dbe-tool sql (single runs): group by the 2 keys with count(*) alone spends 0.45s CPU in the perfect HT, so the per-row state update cost is high even for a single aggregate.

**Plan.** In src/execution/perfect_aggregate_hashtable.cpp and the header src/include/duckdb/execution/perfect_aggregate_hashtable.hpp:
(1) Add a member `idx_t replica_count`, set in the constructor. It is 4 when ALL aggregates have function.order_dependent == AggregateOrderDependent::NOT_ORDER_DEPENDENT, none is DISTINCT, and total_groups * tuple_size * 4 <= ~1MB (use a constant). Otherwise it is 1. Also mark avg as NOT_ORDER_DEPENDENT in extension/core_functions/aggregate/algebraic/avg.cpp (GetAverageAggregate / the decimal binder BindDecimalAvg must keep it, so set it on the returned function after the bind replaces it). avg is order-independent in the same sense sum already is.
(2) Allocate and InitializeStates for total_groups * replica_count tuples. Replica r occupies the tuple indexes [r*total_groups, (r+1)*total_groups). group_is_set keeps only total_groups entries.
(3) AddChunk: keep the group computation and the bounds check. Then set address_data[i] = data + (group + (i & (replica_count-1)) * total_groups) * tuple_size. Leave the rest unchanged (UpdateStates, AddInPlace, filtered path).
(4) Combine(other): for each set group i, and for each replica r of `other`, combine the source tuple (r*total_groups+i) into the target tuple i (the target's replica 0). Batch these into the existing source/target address vectors. Before the global table is used (Combine and Scan run on gstate.ht in physical_perfecthash_aggregate.cpp:170/196), the target's own replicas >0 must either be empty or be folded in. Simplest: the global table also receives AddChunk? Check: it does not, so it only gets Combine into replica 0. Still, add a private FoldReplicas() that combines replicas 1..K-1 into 0 for set groups. Call it at the start of Scan (once, guarded by a flag) and on `other` at the start of Combine, to be robust.
(5) Destroy(): call destructors on all total_groups*replica_count tuples whose group is set (index i % total_groups), or simply on all replicas of set groups.

**Target files.** src/execution/perfect_aggregate_hashtable.cpp, src/include/duckdb/execution/perfect_aggregate_hashtable.hpp, extension/core_functions/aggregate/algebraic/avg.cpp

**Expected gain.** q01: PERFECT_HASH_GROUP_BY 1.5s -> ~0.9-1.1s CPU, roughly 8-15% wall. If the chain theory is wrong, the change is neutral (extra init of 4x states, negligible).

**Generality.** Any low-cardinality GROUP BY on small-range integer or compressed-string keys with sum/count/avg/min/max-style aggregates (the perfect HT path). The more skewed and the fewer the groups, the bigger the gain. Order-dependent aggregates (list, string_agg, first/arg_min ties) are excluded by the gate, so their results are unchanged. Possible slowdown: perfect HTs with many groups (more init and combine work); the size cap limits this.

**Risk.** Low-medium. Correctness depends on combine being correct for all gated aggregates, which parallel execution already relies on. Floating-point sums may differ in the last bits, as they already can across threads. Make sure group_is_set and Destroy cover all replicas so there are no leaks with arena-allocated states.



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
