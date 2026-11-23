# Release report: tpch (SF 1.0, 8 threads)

Generated 2026-11-17T00:07:53-05:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | train (visible) | validation (hidden) | test (held out) | Wrong results |
| --- | --- | ---: | ---: | ---: | ---: |
| v0 | `069cc9f9b5` | 39.2 (1.000x) | 34.8 (1.000x) | 23.3 (1.000x) | 0 |
| v1 | `069cc9f9b5` | 39.4 (0.996x) | 36.0 (0.965x) | 24.0 (0.969x) | 0 |

Measurement noise in this report (v0 timed twice, as itself and as a control): train ±1.5%, val ±3.9%, test ±0.1%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | v1 |
| --- | --- | ---: | ---: |
| train | q02 | 19.6 | 0.98x |
| train | q03 | 32.7 | 1.02x |
| train | q04 | 31.0 | 1.01x |
| train | q05 | 33.1 | 0.99x |
| train | q07 | 35.3 | 1.00x |
| train | q08 | 29.8 | 1.04x |
| train | q09 | 110.9 | 1.01x |
| train | q13 | 96.6 | 1.04x |
| train | q14 | 22.1 | 0.93x |
| train | q16 | 41.9 | 0.95x |
| train | q17 | 20.7 | 0.98x |
| train | q18 | 80.6 | 1.00x |
| train | q19 | 44.2 | 1.01x |
| train | q22 | 40.2 | 0.99x |
| val | q01 | 39.5 | 0.99x |
| val | q11 | 11.2 | 0.94x |
| val | q21 | 95.1 | 0.97x |
| test | q06 | 8.8 | 0.90x |
| test | q10 | 63.8 | 0.98x |
| test | q12 | 23.1 | 0.97x |
| test | q15 | 17.1 | 0.99x |
| test | q20 | 31.0 | 1.02x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
