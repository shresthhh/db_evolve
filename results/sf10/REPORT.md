# Release report: tpch (SF 10.0, 8 threads)

Generated 2026-11-17T23:34:53-05:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | train (visible) | validation (hidden) | test (held out) | Wrong results |
| --- | --- | ---: | ---: | ---: | ---: |
| v0 | `069cc9f9b5` | 267.3 (1.000x) | 245.4 (1.000x) | 167.4 (1.000x) | 0 |
| v1 | `448b47834b` | 253.0 (1.057x) | 239.1 (1.026x) | 162.1 (1.032x) | 0 |
| v2 | `91c2adb134` | 231.5 (1.155x) | 215.5 (1.139x) | 160.9 (1.041x) | 0 |
| v3 | `b6929da26e` | 231.3 (1.156x) | 211.9 (1.158x) | 163.4 (1.025x) | 0 |

Measurement noise in this report (v0 timed twice, as itself and as a control): train ±1.4%, val ±3.3%, test ±1.4%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | v1 | v2 | v3 |
| --- | --- | ---: | ---: | ---: | ---: |
| train | q02 | 75.0 | 0.94x | 0.99x | 0.99x |
| train | q03 | 234.8 | 0.98x | 0.99x | 1.00x |
| train | q04 | 281.9 | 1.03x | 1.40x | 1.41x |
| train | q05 | 262.9 | 1.04x | 1.05x | 1.05x |
| train | q07 | 187.9 | 1.03x | 1.03x | 1.04x |
| train | q08 | 214.8 | 1.01x | 0.99x | 1.00x |
| train | q09 | 1065.7 | 1.83x | 1.88x | 1.88x |
| train | q13 | 749.6 | 1.02x | 1.03x | 1.00x |
| train | q14 | 154.7 | 1.04x | 1.04x | 1.03x |
| train | q16 | 191.1 | 1.06x | 1.04x | 0.95x |
| train | q17 | 204.8 | 1.00x | 1.00x | 0.99x |
| train | q18 | 651.7 | 1.02x | 1.02x | 1.02x |
| train | q19 | 330.7 | 1.01x | 1.89x | 1.93x |
| train | q22 | 173.2 | 0.99x | 1.27x | 1.39x |
| val | q01 | 348.4 | 1.03x | 1.00x | 1.01x |
| val | q11 | 49.2 | 1.04x | 1.02x | 1.03x |
| val | q21 | 863.0 | 1.01x | 1.45x | 1.49x |
| test | q06 | 72.0 | 1.02x | 1.05x | 1.02x |
| test | q10 | 482.9 | 1.01x | 1.03x | 1.01x |
| test | q12 | 187.3 | 1.00x | 1.02x | 1.02x |
| test | q15 | 121.4 | 1.04x | 1.02x | 1.01x |
| test | q20 | 166.3 | 1.09x | 1.07x | 1.07x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
