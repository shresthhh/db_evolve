# Release report: tpcds (SF 10.0, 8 threads)

Generated 2026-11-26T18:49:50+00:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | test (held out) | Wrong results |
| --- | --- | ---: | ---: |
| v0 | `069cc9f9b5` | 96.8 (1.000x) | 3 |
| v1 | `b07ecbf7e7` | 100.6 (0.976x) | 4 |
| v2 | `1320822f46` | 93.1 (1.054x) | 4 |
| v3 | `c9a15ca132` | 87.4 (1.123x) | 4 |

Measurement noise in this report (v0 timed twice, as itself and as a control): test ±1.1%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | v1 | v2 | v3 |
| --- | --- | ---: | ---: | ---: | ---: |
| test | q01 | 47.0 | 1.03x | 1.04x | 1.26x |
| test | q02 | 100.4 | 0.97x | 0.95x | 0.98x |
| test | q03 | 27.6 | 1.04x | 1.18x | 1.26x |
| test | q04 | 966.3 | 1.01x | 1.16x | 1.20x |
| test | q05 | 110.8 | 1.05x | 1.03x | 1.47x |
| test | q06 | 120.1 | 0.92x | 0.92x | 1.30x |
| test | q07 | 76.5 | 1.01x | 1.04x | 1.20x |
| test | q08 | 406.7 | 0.97x | 1.00x | 1.03x |
| test | q09 | 282.0 | 0.99x | 1.00x | 1.02x |
| test | q10 | 48.2 | 0.91x | 1.12x | 1.13x |
| test | q11 | 543.4 | 1.02x | 1.07x | 1.11x |
| test | q12 | 36.6 | 1.05x | 0.89x | 1.08x |
| test | q13 | 125.1 | 1.32x | 1.30x | 1.55x |
| test | q14 | 876.7 | 0.99x | 1.01x | 1.11x |
| test | q15 | 95.9 | 0.99x | 1.34x | 1.44x |
| test | q16 | 29.2 | 0.84x | 1.04x | 1.12x |
| test | q17 | 116.4 | 0.96x | 1.01x | 1.51x |
| test | q18 | nan | nanx | nanx | nanx |
| test | q19 | 64.2 | 0.87x | 1.01x | 1.20x |
| test | q20 | 36.2 | 0.79x | 0.91x | 0.79x |
| test | q21 | 35.0 | 1.01x | 1.06x | 1.16x |
| test | q22 | 2608.7 | 1.03x | 1.06x | 1.10x |
| test | q23 | 1036.5 | 1.00x | 1.07x | 0.99x |
| test | q24 | 79.7 | 1.07x | 1.19x | 1.12x |
| test | q25 | 45.3 | 0.85x | 1.14x | 1.28x |
| test | q26 | 66.5 | 0.93x | 0.94x | 0.93x |
| test | q27 | 61.1 | 0.95x | 0.94x | 1.08x |
| test | q28 | 259.2 | 0.98x | 0.97x | 1.09x |
| test | q29 | 95.5 | 1.04x | 1.07x | 1.18x |
| test | q30 | 85.2 | 1.02x | 1.05x | 1.50x |
| test | q31 | 265.9 | 0.98x | 1.15x | 1.20x |
| test | q32 | 10.3 | 0.93x | 1.13x | 1.22x |
| test | q33 | 64.2 | 0.95x | 1.02x | 1.03x |
| test | q34 | 56.7 | 0.93x | 0.98x | 1.05x |
| test | q35 | 177.8 | 1.00x | 1.07x | 1.42x |
| test | q36 | 251.7 | 1.01x | 1.09x | 1.10x |
| test | q37 | 43.6 | 1.01x | 1.37x | 1.52x |
| test | q38 | 210.3 | 1.01x | 1.15x | 1.21x |
| test | q39 | 132.4 | 1.01x | 1.03x | 1.06x |
| test | q40 | 35.5 | 0.98x | 1.32x | 1.27x |
| test | q41 | 19.4 | 0.90x | 1.27x | 1.22x |
| test | q42 | 39.9 | 0.87x | 1.07x | 1.14x |
| test | q43 | 68.8 | 0.95x | 0.96x | 1.01x |
| test | q44 | 83.1 | 1.00x | 1.05x | 1.23x |
| test | q45 | 89.9 | 0.97x | 1.05x | 1.51x |
| test | q46 | 136.2 | 1.00x | 0.95x | 1.07x |
| test | q47 | 325.9 | 1.02x | 1.02x | 1.07x |
| test | q48 | 122.7 | 0.86x | 0.88x | 1.23x |
| test | q49 | 74.1 | 0.92x | 0.96x | 1.30x |
| test | q50 | 84.2 | 1.90x | 2.06x | 2.32x |
| test | q51 | 1274.7 | 1.01x | 1.01x | 1.03x |
| test | q52 | 31.5 | 0.94x | 1.26x | 1.26x |
| test | q53 | 53.9 | 1.01x | 1.08x | 1.17x |
| test | q54 | 61.1 | 0.91x | 0.93x | 0.91x |
| test | q55 | 34.2 | 0.92x | 1.11x | 1.23x |
| test | q56 | 58.5 | 1.01x | 1.02x | 1.04x |
| test | q57 | 136.3 | 1.02x | 0.99x | 1.05x |
| test | q58 | 65.1 | 0.77x | 0.80x | 0.89x |
| test | q59 | 273.1 | 0.92x | 1.00x | 0.69x |
| test | q60 | 74.7 | 1.00x | 0.99x | 1.06x |
| test | q61 | 54.0 | 0.98x | 1.09x | 1.12x |
| test | q62 | 28.3 | 0.96x | 0.91x | 0.89x |
| test | q63 | 51.9 | 0.96x | 1.07x | 1.06x |
| test | q64 | 308.0 | 1.05x | 1.17x | 1.40x |
| test | q65 | nan | nanx | nanx | nanx |
| test | q66 | 41.7 | 0.93x | 0.95x | 1.09x |
| test | q67 | 2990.2 | 1.02x | 1.07x | 1.07x |
| test | q68 | 108.3 | 0.95x | 0.99x | 1.21x |
| test | q69 | 70.9 | 0.90x | 0.89x | 1.09x |
| test | q70 | 91.7 | 0.87x | 0.87x | 0.82x |
| test | q71 | nan | nanx | nanx | nanx |
| test | q72 | 361.3 | 1.01x | 1.08x | 1.23x |
| test | q73 | 57.8 | 0.97x | 1.22x | 1.36x |
| test | q74 | 351.6 | 0.96x | 0.94x | 1.02x |
| test | q75 | 308.1 | 0.97x | 0.94x | 1.23x |
| test | q76 | 70.7 | 0.95x | 1.02x | 1.08x |
| test | q77 | 54.0 | 0.92x | 0.93x | 1.02x |
| test | q78 | 667.9 | 1.01x | 1.03x | 0.28x |
| test | q79 | 91.3 | 1.00x | 0.93x | 0.88x |
| test | q80 | 144.0 | 1.00x | 1.21x | 1.23x |
| test | q81 | 113.8 | 1.06x | 0.96x | 1.37x |
| test | q82 | 54.1 | 1.03x | 1.18x | 1.28x |
| test | q83 | 24.3 | nanx | nanx | nanx |
| test | q84 | 33.8 | 0.88x | 1.05x | 1.11x |
| test | q85 | 71.8 | 1.31x | 1.34x | 1.30x |
| test | q86 | 42.4 | 0.85x | 0.98x | 0.90x |
| test | q87 | 240.9 | 0.99x | 1.09x | 1.11x |
| test | q88 | 210.8 | 0.97x | 1.06x | 1.10x |
| test | q89 | 65.3 | 0.99x | 1.23x | 1.27x |
| test | q90 | 8.0 | 0.93x | 0.90x | 0.91x |
| test | q91 | 13.6 | 0.87x | 0.98x | 1.07x |
| test | q92 | 19.9 | 0.93x | 1.04x | 1.05x |
| test | q93 | 202.2 | 1.03x | 1.02x | 1.03x |
| test | q94 | 23.2 | 0.84x | 1.10x | 1.10x |
| test | q95 | 526.1 | 1.01x | 1.34x | 1.42x |
| test | q96 | 24.6 | 0.95x | 1.23x | 1.27x |
| test | q97 | 185.0 | 1.00x | 1.01x | 1.02x |
| test | q98 | 105.2 | 0.95x | 0.95x | 0.95x |
| test | q99 | 47.2 | 0.98x | 0.98x | 0.98x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
