# Release report: tpcds (SF 10.0, 8 threads)

Generated 2026-11-26T08:09:35+00:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | test (held out) | Wrong results |
| --- | --- | ---: | ---: |
| v0 | `069cc9f9b5` | 97.0 (1.000x) | 3 |
| v1 | `448b47834b` | 97.1 (0.999x) | 3 |
| v2 | `91c2adb134` | 97.2 (0.998x) | 3 |
| v3 | `b6929da26e` | 95.5 (1.016x) | 3 |

Measurement noise in this report (v0 timed twice, as itself and as a control): test ±1.5%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | v1 | v2 | v3 |
| --- | --- | ---: | ---: | ---: | ---: |
| test | q01 | 52.6 | 1.00x | 1.05x | 1.09x |
| test | q02 | 101.1 | 0.99x | 1.01x | 1.02x |
| test | q03 | 26.4 | 0.98x | 1.01x | 1.02x |
| test | q04 | 957.0 | 1.01x | 1.04x | 1.04x |
| test | q05 | 106.9 | 1.04x | 1.05x | 1.02x |
| test | q06 | 135.2 | 1.03x | 1.09x | 1.04x |
| test | q07 | 80.2 | 1.04x | 1.01x | 1.00x |
| test | q08 | 413.9 | 0.98x | 0.95x | 0.99x |
| test | q09 | 278.9 | 0.99x | 1.03x | 1.01x |
| test | q10 | 46.6 | 1.02x | 1.05x | 1.08x |
| test | q11 | 533.0 | 1.01x | 1.02x | 1.03x |
| test | q12 | 37.0 | 0.92x | 0.97x | 0.95x |
| test | q13 | 122.7 | 1.02x | 1.18x | 1.19x |
| test | q14 | 890.1 | 0.99x | 1.01x | 1.01x |
| test | q15 | 91.0 | 1.01x | 0.95x | 1.00x |
| test | q16 | 31.2 | 0.92x | 0.67x | 1.02x |
| test | q17 | 122.1 | 0.99x | 1.01x | 1.05x |
| test | q18 | nan | nanx | nanx | nanx |
| test | q19 | 67.5 | 1.00x | 0.96x | 0.97x |
| test | q20 | 41.0 | 1.06x | 1.01x | 1.00x |
| test | q21 | 33.7 | 1.01x | 0.98x | 0.95x |
| test | q22 | 2550.2 | 1.05x | 1.05x | 1.06x |
| test | q23 | 1028.7 | 1.02x | 1.01x | 1.03x |
| test | q24 | 77.6 | 1.30x | 1.28x | 1.32x |
| test | q25 | 45.6 | 0.98x | 0.91x | 0.97x |
| test | q26 | 74.5 | 1.04x | 1.01x | 1.05x |
| test | q27 | 62.6 | 0.94x | 1.01x | 0.97x |
| test | q28 | 258.6 | 0.98x | 0.99x | 0.97x |
| test | q29 | 93.8 | 0.98x | 0.97x | 0.98x |
| test | q30 | 82.1 | 0.93x | 0.89x | 0.93x |
| test | q31 | 268.7 | 1.03x | 0.97x | 1.05x |
| test | q32 | 13.0 | 1.19x | 1.18x | 1.30x |
| test | q33 | 69.7 | 1.05x | 1.01x | 1.06x |
| test | q34 | 55.7 | 0.95x | 0.94x | 1.01x |
| test | q35 | 170.4 | 0.97x | 1.00x | 1.01x |
| test | q36 | 245.8 | 1.03x | 1.04x | 1.05x |
| test | q37 | 42.4 | 1.00x | 0.82x | 0.89x |
| test | q38 | 209.1 | 1.03x | 1.00x | 1.03x |
| test | q39 | 131.3 | 1.02x | 1.03x | 1.04x |
| test | q40 | 35.9 | 1.04x | 1.09x | 0.99x |
| test | q41 | 17.7 | 1.03x | 0.97x | 0.91x |
| test | q42 | 40.3 | 1.01x | 1.01x | 1.04x |
| test | q43 | 70.4 | 1.03x | 1.03x | 1.02x |
| test | q44 | 84.1 | 1.02x | 1.00x | 1.03x |
| test | q45 | 89.6 | 1.02x | 1.02x | 0.97x |
| test | q46 | 135.3 | 0.95x | 1.00x | 1.00x |
| test | q47 | 324.7 | 1.02x | 1.01x | 1.07x |
| test | q48 | 124.9 | 1.03x | 0.93x | 0.93x |
| test | q49 | 73.8 | 0.77x | 0.75x | 0.72x |
| test | q50 | 84.2 | 1.59x | 1.54x | 1.57x |
| test | q51 | 1285.8 | 1.02x | 1.01x | 1.03x |
| test | q52 | 32.2 | 1.03x | 1.03x | 1.04x |
| test | q53 | 52.7 | 0.98x | 0.98x | 0.97x |
| test | q54 | 61.8 | 1.04x | 1.04x | 1.04x |
| test | q55 | 33.3 | 0.96x | 0.98x | 1.01x |
| test | q56 | 57.2 | 0.99x | 0.99x | 0.95x |
| test | q57 | 133.4 | 1.00x | 1.01x | 1.01x |
| test | q58 | 67.1 | 1.03x | 1.04x | 1.04x |
| test | q59 | 267.2 | 0.99x | 1.00x | 0.97x |
| test | q60 | 70.8 | 0.98x | 0.95x | 1.04x |
| test | q61 | 50.4 | 0.96x | 0.96x | 0.99x |
| test | q62 | 27.6 | 0.99x | 0.99x | 1.01x |
| test | q63 | 51.4 | 1.01x | 1.01x | 1.01x |
| test | q64 | 303.6 | 1.15x | 1.18x | 1.19x |
| test | q65 | nan | nanx | nanx | nanx |
| test | q66 | 42.4 | 0.99x | 0.99x | 1.02x |
| test | q67 | 2891.4 | 1.01x | 1.01x | 1.05x |
| test | q68 | 104.3 | 0.96x | 0.93x | 0.90x |
| test | q69 | 71.9 | 0.88x | 1.11x | 1.13x |
| test | q70 | 86.9 | 0.93x | 1.02x | 0.99x |
| test | q71 | nan | nanx | nanx | nanx |
| test | q72 | 342.4 | 0.90x | 0.90x | 0.93x |
| test | q73 | 58.2 | 1.02x | 0.99x | 1.00x |
| test | q74 | 347.6 | 1.01x | 0.95x | 0.99x |
| test | q75 | 301.7 | 0.84x | 0.83x | 0.85x |
| test | q76 | 68.9 | 0.99x | 0.93x | 0.94x |
| test | q77 | 54.8 | 0.98x | 0.94x | 0.95x |
| test | q78 | 657.0 | 1.03x | 1.03x | 1.03x |
| test | q79 | 91.2 | 1.00x | 0.97x | 0.98x |
| test | q80 | 148.8 | 1.02x | 1.03x | 1.04x |
| test | q81 | 111.6 | 0.94x | 0.96x | 1.05x |
| test | q82 | 49.7 | 0.89x | 0.86x | 0.83x |
| test | q83 | 26.5 | 1.00x | 0.96x | 0.95x |
| test | q84 | 38.6 | 1.00x | 1.00x | 1.10x |
| test | q85 | 72.7 | 0.96x | 1.26x | 1.24x |
| test | q86 | 43.6 | 0.99x | 0.92x | 0.98x |
| test | q87 | 240.2 | 1.00x | 1.00x | 1.00x |
| test | q88 | 209.9 | 0.99x | 0.99x | 0.99x |
| test | q89 | 64.9 | 0.99x | 0.98x | 1.00x |
| test | q90 | 8.0 | 0.99x | 1.00x | 0.98x |
| test | q91 | 13.6 | 1.00x | 0.97x | 1.00x |
| test | q92 | 19.4 | 0.95x | 1.00x | 0.97x |
| test | q93 | 197.1 | 1.03x | 1.04x | 1.07x |
| test | q94 | 23.1 | 0.92x | 1.04x | 1.04x |
| test | q95 | 508.5 | 0.98x | 0.97x | 1.26x |
| test | q96 | 24.5 | 1.00x | 1.03x | 1.01x |
| test | q97 | 182.7 | 1.02x | 0.99x | 1.00x |
| test | q98 | 114.3 | 0.93x | 1.01x | 0.96x |
| test | q99 | 46.0 | 0.97x | 0.99x | 0.97x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
