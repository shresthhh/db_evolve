# Release report: tpcds (SF 10.0, 8 threads)

Generated 2026-11-19T02:06:11-05:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | test (held out) | Wrong results |
| --- | --- | ---: | ---: |
| v0 | `069cc9f9b5` | 171.8 (1.000x) | 3 |
| v1 | `448b47834b` | 168.9 (1.017x) | 3 |
| v2 | `91c2adb134` | 168.0 (1.023x) | 3 |
| v3 | `b6929da26e` | 166.2 (1.034x) | 3 |

Measurement noise in this report (v0 timed twice, as itself and as a control): test ±2.4%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | v1 | v2 | v3 |
| --- | --- | ---: | ---: | ---: | ---: |
| test | q01 | 72.0 | 0.94x | 0.95x | 0.99x |
| test | q02 | 194.3 | 0.97x | 1.00x | 1.03x |
| test | q03 | 45.6 | 0.98x | 1.04x | 1.01x |
| test | q04 | 1710.7 | 1.04x | 1.02x | 1.02x |
| test | q05 | 195.7 | 0.99x | 1.02x | 1.02x |
| test | q06 | 181.2 | 0.92x | 0.96x | 0.84x |
| test | q07 | 122.4 | 0.96x | 0.94x | 0.97x |
| test | q08 | 586.4 | 1.10x | 1.05x | 1.05x |
| test | q09 | 564.6 | 1.04x | 1.03x | 1.03x |
| test | q10 | 98.3 | 1.01x | 1.03x | 1.05x |
| test | q11 | 979.4 | 1.01x | 1.00x | 0.99x |
| test | q12 | 65.4 | 1.25x | 1.11x | 0.99x |
| test | q13 | 226.5 | 1.08x | 1.16x | 1.20x |
| test | q14 | 1867.4 | 1.09x | 1.05x | 1.03x |
| test | q15 | 92.3 | 1.03x | 1.05x | 1.10x |
| test | q16 | 40.2 | 1.04x | 0.66x | 1.19x |
| test | q17 | 188.3 | 1.00x | 1.02x | 1.00x |
| test | q18 | nan | nanx | nanx | nanx |
| test | q19 | 100.4 | 0.98x | 0.99x | 0.99x |
| test | q20 | 52.7 | 0.88x | 0.87x | 0.83x |
| test | q21 | 38.3 | 1.03x | 1.01x | 1.04x |
| test | q22 | 3902.0 | 0.99x | 0.98x | 0.92x |
| test | q23 | 2299.7 | 1.03x | 1.05x | 0.98x |
| test | q24 | 198.9 | 1.48x | 1.42x | 1.23x |
| test | q25 | 101.7 | 1.25x | 1.19x | 1.03x |
| test | q26 | 135.3 | 1.07x | 1.13x | 1.12x |
| test | q27 | 110.4 | 1.07x | 1.07x | 0.99x |
| test | q28 | 498.8 | 0.98x | 1.00x | 0.97x |
| test | q29 | 184.5 | 0.99x | 1.03x | 1.01x |
| test | q30 | 106.7 | 1.01x | 1.04x | 0.98x |
| test | q31 | 453.7 | 1.05x | 1.00x | 0.96x |
| test | q32 | 17.1 | 1.17x | 0.86x | 1.00x |
| test | q33 | 92.6 | 0.98x | 0.91x | 0.98x |
| test | q34 | 87.6 | 0.88x | 0.93x | 0.93x |
| test | q35 | 366.3 | 1.02x | 1.16x | 1.17x |
| test | q36 | 441.7 | 1.08x | 0.99x | 1.01x |
| test | q37 | 51.3 | 0.97x | 1.06x | 1.00x |
| test | q38 | 393.8 | 1.04x | 0.98x | 0.99x |
| test | q39 | 250.3 | 1.02x | 0.94x | 1.00x |
| test | q40 | 56.9 | 0.90x | 0.96x | 0.92x |
| test | q41 | 36.3 | 0.98x | 1.03x | 1.13x |
| test | q42 | 70.2 | 1.10x | 1.05x | 1.07x |
| test | q43 | 133.4 | 0.97x | 1.02x | 1.04x |
| test | q44 | 143.3 | 0.97x | 1.02x | 1.01x |
| test | q45 | 142.0 | 1.00x | 1.11x | 0.97x |
| test | q46 | 218.8 | 1.07x | 1.09x | 1.04x |
| test | q47 | 659.4 | 1.00x | 1.00x | 1.00x |
| test | q48 | 245.8 | 1.03x | 0.95x | 0.94x |
| test | q49 | 141.0 | 0.91x | 0.92x | 0.90x |
| test | q50 | 170.5 | 1.68x | 1.73x | 1.74x |
| test | q51 | 2351.6 | 1.05x | 1.03x | 0.95x |
| test | q52 | 59.2 | 0.91x | 0.94x | 0.90x |
| test | q53 | 106.6 | 0.94x | 1.04x | 1.00x |
| test | q54 | 99.0 | 0.92x | 0.96x | 0.95x |
| test | q55 | 62.2 | 0.95x | 0.97x | 1.01x |
| test | q56 | 101.7 | 1.01x | 0.99x | 0.95x |
| test | q57 | 265.7 | 0.99x | 1.01x | 0.98x |
| test | q58 | 105.1 | 0.97x | 0.96x | 0.95x |
| test | q59 | 605.9 | 0.99x | 1.05x | 1.03x |
| test | q60 | 131.3 | 1.12x | 1.09x | 1.10x |
| test | q61 | 99.6 | 1.09x | 1.11x | 1.13x |
| test | q62 | 70.8 | 1.13x | 1.21x | 1.25x |
| test | q63 | 100.0 | 1.11x | 1.05x | 1.05x |
| test | q64 | 534.1 | 1.16x | 1.20x | 1.21x |
| test | q65 | nan | nanx | nanx | nanx |
| test | q66 | 92.7 | 1.05x | 1.09x | 1.04x |
| test | q67 | 7084.4 | 0.99x | 1.06x | 1.10x |
| test | q68 | 203.1 | 1.07x | 0.95x | 1.11x |
| test | q69 | 120.4 | 0.99x | 1.26x | 1.33x |
| test | q70 | 187.1 | 1.02x | 0.97x | 1.03x |
| test | q71 | nan | nanx | nanx | nanx |
| test | q72 | 710.2 | 0.97x | 0.94x | 0.95x |
| test | q73 | 108.2 | 1.21x | 1.11x | 1.11x |
| test | q74 | 719.0 | 0.99x | 1.06x | 1.02x |
| test | q75 | 568.8 | 0.90x | 0.93x | 0.99x |
| test | q76 | 122.5 | 1.02x | 0.97x | 1.04x |
| test | q77 | 108.5 | 0.99x | 1.05x | 1.08x |
| test | q78 | 1283.7 | 1.03x | 1.03x | 1.03x |
| test | q79 | 187.2 | 1.05x | 1.09x | 1.01x |
| test | q80 | 286.1 | 0.95x | 0.98x | 1.01x |
| test | q81 | 142.1 | 0.79x | 0.83x | 0.84x |
| test | q82 | 76.0 | 1.05x | 1.04x | 1.06x |
| test | q83 | 37.8 | 0.90x | 1.05x | 1.07x |
| test | q84 | 34.4 | 0.86x | 0.89x | 1.00x |
| test | q85 | 119.5 | 0.97x | 1.46x | 1.49x |
| test | q86 | 77.0 | 0.94x | 1.02x | 1.00x |
| test | q87 | 446.0 | 0.96x | 0.98x | 1.02x |
| test | q88 | 389.1 | 1.00x | 1.00x | 1.04x |
| test | q89 | 121.6 | 0.95x | 0.93x | 0.96x |
| test | q90 | 16.3 | 0.95x | 1.02x | 1.03x |
| test | q91 | 29.3 | 1.00x | 1.01x | 1.02x |
| test | q92 | 32.9 | 1.05x | 1.01x | 0.99x |
| test | q93 | 309.0 | 0.96x | 0.98x | 0.97x |
| test | q94 | 49.3 | 0.97x | 0.92x | 1.07x |
| test | q95 | 1105.8 | 0.96x | 0.96x | 1.26x |
| test | q96 | 48.2 | 1.04x | 0.96x | 0.94x |
| test | q97 | 405.4 | 1.06x | 1.01x | 1.05x |
| test | q98 | 176.3 | 1.18x | 1.05x | 1.19x |
| test | q99 | 82.0 | 0.99x | 1.01x | 1.05x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
