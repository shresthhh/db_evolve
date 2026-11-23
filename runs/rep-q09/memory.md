# Memory (db_evolve, q09 specialisation run)

## Status: end of gen1 (r6), best 2.266x (E0001 contains sel -29%, E0002 BF first key multi-key HJ -22%, E0004 exact bitmap BF -20%)
- E0003 (offset-aware min/max + HASHED BF through CM compress) RETIRED: bench +4.7%. Hashing 15M keys into random 5MB BF too costly.
- E0005 (same pushdown, EXACT bitmap only, offset-shifted) RETIRED only by noise gate: bench -7.9% (local -14.3%), hidden ok.
  GOOD IDEA, real gain.
- r6 final dispatch: COMBINED issue = E0005 re-land + group prefetch in JoinHashTable probe/build (no prefetch existed in src/).
  An earlier r6 planner attempt had dispatched prefetch alone, but no ledger entry appeared (the session likely died).
  If the combined change is accepted, check the ledger for which part gave the gain. If it shows ~E0005-only gain, prefetch is ~0%
  (OoO already overlaps the misses) and the HJ cost is elsewhere (payload gather / TupleData sink).

## q09 HOT profile (r6 slot binary had E0005: orders scan 2.94M rows), CPU seconds summed over threads, ~460ms wall
- HJ o_orderkey=l_orderkey 1.02s (build 3.27M from lineitem side, ~8M-entry 64MB pointer table; probe 2.94M). Biggest op.
  Without E0005: 1.39-1.56s with 15M probe rows. Build vs probe not decomposed yet.
- lineitem scan 0.77s (60M -> 3.27M exact via bitmap on l_partkey); lineitem⋈(part⋈ps) HJ 0.51s (2 keys, build 436K)
- HASH_GROUP_BY 0.19-0.22s (175 groups) + CM compress proj (string->uhugeint n_name, year->utinyint) 0.08s + proj 0.035s
- part scan (contains) 0.16s; orders scan 0.10s; partsupp scan 0.06s; rest tiny.
- Cold `dbe-tool profile` numbers are ~2x inflated & distort shares; use hot JSON trick below.
- Hot micro: lineitem count(*) WHERE l_partkey%20=3 ~55ms wall; + selecting 5 more bitpacked cols at 5% -> ~175ms.

## Remaining ideas (gen2)
- Orders HJ build cost: decompose sink (TupleData append) vs Finalize (InsertHashesLoop, join_hashtable.cpp:591) vs probe.
  Perfect HJ is not applicable (3.27M build over a 60M key range).
- Agg ~0.3s total for 175 groups: small-group/perfect agg path, or skip the string CM compress before a tiny-group agg. Not checked in code.
- Sibling: sparse-select decode tweaks on bitpacked scan gave 0%.

## Codebase facts
- JSON profile trick (hot): one dbe-tool sql call: PRAGMA enable_profiling='json'; SET profiling_output='/tmp/x.json';
  run query twice; PRAGMA disable_profiling; SELECT unnest(regexp_extract_all(regexp_replace(content,'\s+',' ','g'),
  '"operator_timing": [0-9.e-]+|"operator_name": "[A-Z_ ]+"|"operator_cardinality": [0-9]+|"Conditions": "[^"]*"',0))
  FROM read_text('/tmp/x.json')   (output order = preorder tree, timing precedes name)
- dbe-tool: no shell variables; pipes to grep need approval (avoid). Each sql call is a fresh process.
- The slot binary may be from the last experiment, not the current best.
- Optimizer order: STATISTICS_PROPAGATION (adds CM compress projections) runs BEFORE JOIN_FILTER_PUSHDOWN.
  PushdownJoinFilterExpression (join_filter_pushdown_optimizer.cpp:23) passes only colref and integral casts.
- TopN optimizer and RowGroupPruner reuse GetPushdownFilterTargets: any value-transforming pass-through must be rejected there.
- FinalizeFilters (physical_hash_join.cpp:870): min/max -> SelectivityOptionalFilter, IN for small HTs, BF only if !has_cast &&
  first key && CanUseBloomFilter (:761). Deferred BF push at HT finalize (:588 PushBloomFilter :788).
  TrySetExactBloomFilterRange (:845): exact bitmap if same physical type, range<2^31, <=128 bits/key.
- JoinHashTable probe: GetRowPointersInternal (join_hashtable.cpp:255) -> ProbeForPointersInternal (:188, linear probing with
  salts if capacity > USE_SALT_THRESHOLD) -> row_matcher_build.Match. Build: Finalize (:792) -> InsertHashes (:717, also
  inserts BF keys) -> InsertHashesLoop (:591, CAS inserts). Pointer table = PointerTableCapacity(Count()) 8B entries.
- RowGroup::Scan (row_group.cpp:694): filter cols via Filter() in adaptive order, others via Select(sel).
- BF (planner/filter/bloom_filter.cpp): hashed 12 bits/key; exact mode via SetKeyRange (E0004).
- Hash<uint32>(c) == Hash<int64>(k) for 0<=v<2^32 (hash.hpp:36-60).
- Testing tip: range()/CTE sources don't get pushed filters; use real tables vs `col+0` keys to block pushdown.
- Adding `hash(o_orderkey)%50=0` to q09 flips orders to build side -> not usable to isolate HJ build cost.
- Bench noise on q09 can exceed ~8%: gains below ~10% risk being retired by the noise gate; bundle related gains.

## Exhausted / retired
- Multi-key BF: DONE (E0002). contains selectivity: DONE (E0001). Exact bitmap BF: DONE (E0004).
- Hashed BF through CM offset: retired E0003 (+4.7%). Exact-only variant E0005: real gain, re-dispatched combined in r6.
