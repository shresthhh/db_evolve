# Release report: tpch (SF 10.0, 8 threads)

Generated 2026-11-17T16:50:39-05:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | train (visible) | validation (hidden) | test (held out) | Wrong results |
| --- | --- | ---: | ---: | ---: | ---: |
| v0 | `069cc9f9b5` | 261.9 (1.000x) | 240.6 (1.000x) | 166.6 (1.000x) | 0 |

Measurement noise in this report (v0 timed twice, as itself and as a control): train ±1.2%, val ±0.6%, test ±2.0%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms |  |
| --- | --- | ---: |  |
| train | q02 | 76.2 |  |
| train | q03 | 227.8 |  |
| train | q04 | 263.0 |  |
| train | q05 | 255.9 |  |
| train | q07 | 185.4 |  |
| train | q08 | 209.7 |  |
| train | q09 | 1074.9 |  |
| train | q13 | 740.1 |  |
| train | q14 | 148.8 |  |
| train | q16 | 182.4 |  |
| train | q17 | 199.1 |  |
| train | q18 | 634.3 |  |
| train | q19 | 329.0 |  |
| train | q22 | 175.2 |  |
| val | q01 | 336.5 |  |
| val | q11 | 48.6 |  |
| val | q21 | 852.0 |  |
| test | q06 | 70.3 |  |
| test | q10 | 487.8 |  |
| test | q12 | 187.9 |  |
| test | q15 | 118.8 |  |
| test | q20 | 167.8 |  |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
