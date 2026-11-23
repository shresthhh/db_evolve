# Planner memory (q13 specialisation run)

## Profile facts (gen1 r1, baseline 807.6 ms q13)
- orders scan + NOT LIKE '%a%b%' filter: 2.58s CPU (largest; 2.51s in r3 profile)
- inner HASH_GROUP_BY on c_custkey (1.5M groups, count over 14.8M join rows): 2.51s -> 2.36s in r3 profile
- HASH_JOIN RIGHT o_custkey=c_custkey (build 1.5M customers): 1.76s -> ~0.24s after E0001
- outer group by c_count: 0.06s (negligible)
- join keys pass through compress/decompress projections (uinteger compress)
- Query is customer LEFT JOIN orders; optimizer flips it to RIGHT join building customer.
- Perfect HA gate: plan_aggregate.cpp CanUsePerfectHashAggregate (line ~127), needs group stats min/max;
  int types only; bits limited by perfect_ht_threshold.

## Results
- E0001 perfect HJ RIGHT: ACCEPTED, q13 -18% (631.7 ms, 1.221x). Key lesson: per-slot byte match array
  copied into HT rows at PrepareScanHT beat writing found_match in probe (-17.8% vs -11.6%).
- E0002 SIMD strstr (first+last byte, overlapping tail): RETIRED, bench -3% (implementer's own runs -6..-12%,
  very noisy). Good idea, below the -5% bar here. Could be retried combined with something else on the
  scan (e.g. AVX2, short-haystack SWAR), but don't re-run alone.
- Follow-up idea from implementer: LEFT joins (probe kept) could use perfect path too (not needed for q13).

## Prior-run knowledge (other db_evolve runs on the same engine, measured)
- Large perfect HA up to 22 bits: -18.6% only with a parallel combine and a parallel source; serial gave 3.6%.
- No gain before: FSST heap reuse (0%), BitPacking sparse select.

## Plan of record
r1: perfect HJ RIGHT (accepted). r2: SIMD strstr (retired, -3%). r3: large perfect HA (parallel combine+source) dispatched.
r4+: if HA lands, the scan (2.5s) is the only big remaining cost: options are FSST-compressed filter
(lazy decode; see global memory fsst-scan-lazy-decode), strstr SIMD v2 (AVX2 + short-string path),
or fusing count into the perfect HJ probe (aggregate on build key directly).
If a change measures ~0%, suspect a silent gate before retiring the idea.
