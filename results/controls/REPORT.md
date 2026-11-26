# Release report: tpch (SF 10.0, 8 threads)

Generated 2026-11-26T04:49:07-05:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | train (visible) | validation (hidden) | test (held out) | Wrong results |
| --- | --- | ---: | ---: | ---: | ---: |
| v0 | `069cc9f9b5` | 266.6 (1.000x) | 242.1 (1.000x) | 166.2 (1.000x) | 0 |
| q09 | `a496c6c900` | 240.8 (1.107x) | 234.9 (1.030x) | 160.5 (1.036x) | 0 |
| q13 | `6eb234ec7c` | 301.2 (0.885x) | 243.0 (0.996x) | 153.1 (1.086x) | 0 |
| q16 | `0ad9b3c529` | 254.2 (1.049x) | 240.1 (1.008x) | 165.0 (1.008x) | 0 |
| spec-q09 | `f0d9e1f951` | 244.5 (1.090x) | 235.5 (1.028x) | 160.9 (1.033x) | 0 |
| spec-q13 | `6d8309dd17` | 302.6 (0.881x) | 236.9 (1.022x) | 154.6 (1.075x) | 0 |
| spec-q16 | `084cba35c5` | 265.2 (1.006x) | 241.0 (1.005x) | 165.7 (1.004x) | 0 |
| sf10 | `b6929da26e` | 232.1 (1.149x) | 211.4 (1.145x) | 163.1 (1.019x) | 0 |
| joint48 | `c9a15ca132` | 121.3 (2.199x) | 188.0 (1.287x) | 107.3 (1.550x) | 0 |
| agent-k1-g1 | `a0c0f31d55` | 222.5 (1.198x) | 213.8 (1.132x) | 145.1 (1.146x) | 0 |

Measurement noise in this report (v0 timed twice, as itself and as a control): train ±0.6%, val ±1.0%, test ±0.0%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | q09 | q13 | q16 | spec-q09 | spec-q13 | spec-q16 | sf10 | joint48 | agent-k1-g1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | q02 | 75.9 | 1.03x | 1.04x | 0.97x | 1.05x | 0.97x | 1.05x | 1.00x | 1.50x | 1.96x |
| train | q03 | 238.9 | 1.28x | 1.02x | 1.33x | 1.06x | 1.02x | 1.01x | 1.00x | 1.86x | 1.38x |
| train | q04 | 279.9 | 1.20x | 0.98x | 1.15x | 1.07x | 1.04x | 0.99x | 1.36x | 2.76x | 1.26x |
| train | q05 | 253.5 | 1.01x | 0.99x | 0.99x | 1.03x | 0.99x | 0.99x | 1.00x | 2.10x | 1.05x |
| train | q07 | 181.5 | 1.04x | 0.98x | 1.05x | 1.02x | 0.97x | 1.00x | 0.97x | 1.37x | 1.07x |
| train | q08 | 211.8 | 0.94x | 0.99x | 0.96x | 1.00x | 0.93x | 0.95x | 0.99x | 2.02x | 1.02x |
| train | q09 | 1135.0 | 2.31x | 0.98x | 1.06x | 2.08x | 1.02x | 1.00x | 1.87x | 3.81x | 2.47x |
| train | q13 | 761.7 | 1.03x | 1.56x | 1.01x | 1.10x | 1.61x | 1.01x | 1.03x | 3.27x | 1.62x |
| train | q14 | 150.0 | 1.00x | 0.64x | 1.00x | 1.06x | 0.61x | 0.98x | 1.00x | 1.80x | 0.65x |
| train | q16 | 182.9 | 1.11x | 0.96x | 1.22x | 1.05x | 0.94x | 1.10x | 1.01x | 1.12x | 1.10x |
| train | q17 | 210.2 | 1.01x | 0.37x | 1.01x | 1.03x | 0.38x | 1.01x | 1.01x | 2.26x | 0.37x |
| train | q18 | 652.7 | 1.01x | 0.87x | 1.02x | 1.01x | 0.91x | 1.01x | 1.02x | 3.70x | 1.12x |
| train | q19 | 332.3 | 1.00x | 0.60x | 0.99x | 1.02x | 0.59x | 0.99x | 1.86x | 3.62x | 2.08x |
| train | q22 | 171.6 | 1.00x | 1.00x | 0.99x | 0.98x | 0.98x | 0.98x | 1.44x | 1.81x | 1.29x |
| val | q01 | 346.6 | 1.00x | 1.01x | 0.99x | 1.01x | 1.02x | 1.00x | 1.01x | 1.02x | 1.15x |
| val | q11 | 46.2 | 1.01x | 1.00x | 1.00x | 1.01x | 1.02x | 1.00x | 1.01x | 1.08x | 0.97x |
| val | q21 | 886.2 | 1.08x | 0.98x | 1.04x | 1.06x | 1.02x | 1.01x | 1.48x | 1.94x | 1.29x |
| test | q06 | 73.1 | 1.02x | 1.03x | 1.02x | 1.00x | 1.02x | 1.03x | 1.04x | 1.21x | 1.03x |
| test | q10 | 489.7 | 0.98x | 1.00x | 1.01x | 1.03x | 0.98x | 1.00x | 0.99x | 1.80x | 1.10x |
| test | q12 | 184.9 | 0.99x | 1.00x | 0.97x | 1.05x | 0.98x | 0.99x | 1.00x | 1.21x | 1.03x |
| test | q15 | 116.0 | 1.00x | 1.47x | 1.01x | 1.00x | 1.46x | 0.99x | 1.00x | 2.09x | 1.43x |
| test | q20 | 165.3 | 1.20x | 1.00x | 1.02x | 1.09x | 1.01x | 1.01x | 1.07x | 1.63x | 1.18x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
