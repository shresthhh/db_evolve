# Release report: tpcds (SF 10.0, 8 threads)

Generated 2026-11-26T08:30:08+00:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | test (held out) | Wrong results |
| --- | --- | ---: | ---: |
| v0 | `069cc9f9b5` | 98.6 (1.000x) | 3 |
| v1 | `a0c0f31d55` | 81.1 (1.216x) | 3 |

Measurement noise in this report (v0 timed twice, as itself and as a control): test ±2.0%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | v1 |
| --- | --- | ---: | ---: |
| test | q01 | 49.2 | 1.13x |
| test | q02 | 100.5 | 0.90x |
| test | q03 | 27.0 | 1.09x |
| test | q04 | 966.5 | 1.13x |
| test | q05 | 104.6 | 1.18x |
| test | q06 | 128.6 | 1.67x |
| test | q07 | 78.0 | 1.36x |
| test | q08 | 398.6 | 2.79x |
| test | q09 | 278.3 | 1.04x |
| test | q10 | 46.9 | 1.00x |
| test | q11 | 551.0 | 1.08x |
| test | q12 | 39.7 | 1.94x |
| test | q13 | 123.0 | 1.39x |
| test | q14 | 883.9 | 1.14x |
| test | q15 | 91.8 | 1.24x |
| test | q16 | 32.0 | 1.05x |
| test | q17 | 122.3 | 1.12x |
| test | q18 | nan | nanx |
| test | q19 | 67.1 | 1.22x |
| test | q20 | 43.9 | 1.84x |
| test | q21 | 37.4 | 1.22x |
| test | q22 | 2654.8 | 1.03x |
| test | q23 | 1033.9 | 0.98x |
| test | q24 | 80.2 | 1.43x |
| test | q25 | 46.8 | 1.28x |
| test | q26 | 71.2 | 1.25x |
| test | q27 | 63.9 | 1.11x |
| test | q28 | 257.7 | 0.99x |
| test | q29 | 94.2 | 1.17x |
| test | q30 | 88.2 | 2.32x |
| test | q31 | 265.1 | 1.92x |
| test | q32 | 10.7 | 1.48x |
| test | q33 | 69.1 | 1.31x |
| test | q34 | 55.8 | 1.08x |
| test | q35 | 177.9 | 1.17x |
| test | q36 | 248.3 | 2.59x |
| test | q37 | 44.5 | 2.35x |
| test | q38 | 212.9 | 1.15x |
| test | q39 | 131.9 | 1.07x |
| test | q40 | 35.3 | 1.22x |
| test | q41 | 19.8 | 1.90x |
| test | q42 | 43.7 | 1.20x |
| test | q43 | 69.4 | 1.11x |
| test | q44 | 82.0 | 1.13x |
| test | q45 | 95.8 | 1.90x |
| test | q46 | 138.4 | 1.30x |
| test | q47 | 320.2 | 1.06x |
| test | q48 | 122.9 | 0.93x |
| test | q49 | 74.4 | 0.93x |
| test | q50 | 84.3 | 1.94x |
| test | q51 | 1281.3 | 1.01x |
| test | q52 | 32.4 | 1.03x |
| test | q53 | 54.2 | 1.27x |
| test | q54 | 62.4 | 1.16x |
| test | q55 | 35.1 | 1.11x |
| test | q56 | 59.7 | 1.13x |
| test | q57 | 137.3 | 1.08x |
| test | q58 | 66.7 | 1.12x |
| test | q59 | 275.8 | 1.02x |
| test | q60 | 73.2 | 1.18x |
| test | q61 | 53.1 | 1.09x |
| test | q62 | 27.8 | 1.01x |
| test | q63 | 51.4 | 1.31x |
| test | q64 | 310.3 | 1.32x |
| test | q65 | nan | nanx |
| test | q66 | 42.5 | 0.99x |
| test | q67 | 3052.1 | 1.04x |
| test | q68 | 106.2 | 1.02x |
| test | q69 | 77.4 | 1.22x |
| test | q70 | 89.2 | 0.91x |
| test | q71 | nan | nanx |
| test | q72 | 343.5 | 1.06x |
| test | q73 | 56.5 | 1.01x |
| test | q74 | 375.4 | 1.17x |
| test | q75 | 316.1 | 1.08x |
| test | q76 | 72.7 | 1.07x |
| test | q77 | 55.6 | 0.99x |
| test | q78 | 677.6 | 1.11x |
| test | q79 | 92.2 | 0.99x |
| test | q80 | 147.5 | 1.09x |
| test | q81 | 114.6 | 1.85x |
| test | q82 | 58.8 | 1.78x |
| test | q83 | 27.2 | 1.40x |
| test | q84 | 37.4 | 1.58x |
| test | q85 | 75.5 | 1.71x |
| test | q86 | 46.6 | 1.24x |
| test | q87 | 243.2 | 1.05x |
| test | q88 | 210.5 | 0.98x |
| test | q89 | 65.5 | 1.13x |
| test | q90 | 8.0 | 0.92x |
| test | q91 | 13.4 | 1.06x |
| test | q92 | 19.1 | 1.01x |
| test | q93 | 202.0 | 1.30x |
| test | q94 | 23.7 | 0.95x |
| test | q95 | 523.5 | 1.06x |
| test | q96 | 24.3 | 0.95x |
| test | q97 | 191.6 | 1.10x |
| test | q98 | 118.6 | 1.17x |
| test | q99 | 48.6 | 0.98x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
