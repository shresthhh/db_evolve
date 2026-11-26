# Release report: tpch (SF 10.0, 8 threads)

Generated 2026-11-26T03:27:50-05:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | train (visible) | validation (hidden) | test (held out) | Wrong results |
| --- | --- | ---: | ---: | ---: | ---: |
| v0 | `069cc9f9b5` | 263.6 (1.000x) | 241.2 (1.000x) | 164.4 (1.000x) | 0 |
| v1 | `b07ecbf7e7` | 216.3 (1.219x) | 223.1 (1.081x) | 159.6 (1.030x) | 0 |
| v2 | `1320822f46` | 160.3 (1.644x) | 214.7 (1.123x) | 126.9 (1.295x) | 0 |
| v3 | `c9a15ca132` | 120.2 (2.192x) | 187.3 (1.288x) | 107.9 (1.524x) | 0 |

Measurement noise in this report (v0 timed twice, as itself and as a control): train ±1.6%, val ±2.0%, test ±1.6%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | v1 | v2 | v3 |
| --- | --- | ---: | ---: | ---: | ---: |
| train | q02 | 76.3 | 1.00x | 1.44x | 1.51x |
| train | q03 | 228.8 | 1.24x | 1.38x | 1.80x |
| train | q04 | 276.2 | 1.17x | 1.84x | 2.75x |
| train | q05 | 250.0 | 0.99x | 1.37x | 2.07x |
| train | q07 | 183.7 | 1.07x | 1.17x | 1.37x |
| train | q08 | 213.0 | 1.00x | 1.39x | 2.00x |
| train | q09 | 1093.4 | 2.28x | 2.80x | 3.65x |
| train | q13 | 741.9 | 1.43x | 2.02x | 3.21x |
| train | q14 | 148.9 | 1.01x | 1.45x | 1.79x |
| train | q16 | 184.4 | 1.07x | 1.08x | 1.13x |
| train | q17 | 206.5 | 0.96x | 1.88x | 2.25x |
| train | q18 | 643.5 | 1.21x | 1.27x | 3.63x |
| train | q19 | 328.5 | 2.09x | 3.67x | 3.84x |
| train | q22 | 170.2 | 1.22x | 1.68x | 1.85x |
| val | q01 | 344.1 | 0.99x | 1.01x | 1.00x |
| val | q11 | 45.5 | 0.99x | 1.02x | 1.08x |
| val | q21 | 896.2 | 1.29x | 1.37x | 1.98x |
| test | q06 | 71.4 | 1.01x | 1.12x | 1.17x |
| test | q10 | 475.1 | 0.97x | 1.21x | 1.71x |
| test | q12 | 182.7 | 0.96x | 1.01x | 1.17x |
| test | q15 | 117.1 | 1.00x | 1.88x | 2.12x |
| test | q20 | 165.6 | 1.22x | 1.42x | 1.65x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
