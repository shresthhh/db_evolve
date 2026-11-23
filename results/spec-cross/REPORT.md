# Release report: tpch (SF 10.0, 8 threads)

Generated 2026-11-22T18:37:25-05:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | train (visible) | validation (hidden) | test (held out) | Wrong results |
| --- | --- | ---: | ---: | ---: | ---: |
| v0 | `069cc9f9b5` | 270.6 (1.000x) | 250.3 (1.000x) | 171.1 (1.000x) | 0 |
| q01 | `212b144ff9` | 280.8 (0.963x) | 239.7 (1.044x) | 177.8 (0.962x) | 0 |
| q02 | `cef9fd6aec` | 266.4 (1.016x) | 249.4 (1.004x) | 171.9 (0.995x) | 0 |
| q09 | `f0d9e1f951` | 252.6 (1.071x) | 241.2 (1.038x) | 163.8 (1.044x) | 0 |
| q13 | `6d8309dd17` | 315.4 (0.858x) | 249.7 (1.003x) | 157.6 (1.085x) | 0 |
| q16 | `084cba35c5` | 275.9 (0.980x) | 250.6 (0.999x) | 172.4 (0.992x) | 0 |
| q18 | `d6c752b412` | 276.9 (0.977x) | 255.7 (0.979x) | 171.0 (1.000x) | 0 |
| q19 | `cca0c610d4` | 262.8 (1.029x) | 251.5 (0.995x) | 169.8 (1.007x) | 0 |
| q21 | `b0c8337757` | 259.8 (1.041x) | 236.2 (1.060x) | 166.4 (1.028x) | 0 |

Measurement noise in this report (v0 timed twice, as itself and as a control): train ±2.5%, val ±0.7%, test ±0.9%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | q01 | q02 | q09 | q13 | q16 | q18 | q19 | q21 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | q02 | 77.2 | 0.89x | 1.97x | 0.93x | 0.87x | 0.98x | 0.92x | 0.99x | 0.90x |
| train | q03 | 232.8 | 0.95x | 0.93x | 0.98x | 0.92x | 0.95x | 0.93x | 0.94x | 1.27x |
| train | q04 | 279.3 | 0.99x | 0.95x | 1.07x | 0.96x | 0.98x | 0.98x | 0.99x | 1.16x |
| train | q05 | 258.4 | 0.95x | 0.95x | 1.01x | 0.95x | 0.98x | 1.01x | 0.93x | 1.00x |
| train | q07 | 187.0 | 0.95x | 0.93x | 1.02x | 0.99x | 0.98x | 0.99x | 0.94x | 1.08x |
| train | q08 | 217.3 | 0.96x | 0.98x | 0.99x | 1.00x | 1.00x | 0.99x | 0.96x | 1.00x |
| train | q09 | 1130.7 | 1.01x | 0.97x | 2.07x | 0.94x | 0.96x | 0.95x | 0.99x | 1.06x |
| train | q13 | 753.3 | 0.91x | 0.93x | 1.06x | 1.45x | 0.97x | 0.90x | 0.92x | 0.96x |
| train | q14 | 155.3 | 0.96x | 1.02x | 1.06x | 0.70x | 0.98x | 0.96x | 0.97x | 0.98x |
| train | q16 | 190.2 | 0.97x | 0.93x | 1.06x | 0.85x | 1.06x | 0.99x | 1.01x | 1.03x |
| train | q17 | 204.1 | 0.96x | 0.97x | 1.01x | 0.36x | 0.90x | 0.95x | 0.99x | 0.96x |
| train | q18 | 654.3 | 1.00x | 0.97x | 0.99x | 0.84x | 0.95x | 1.12x | 1.00x | 0.98x |
| train | q19 | 341.0 | 0.96x | 0.95x | 1.01x | 0.65x | 1.01x | 0.99x | 2.14x | 1.00x |
| train | q22 | 186.5 | 1.03x | 1.07x | 1.04x | 1.02x | 1.03x | 1.03x | 1.03x | 1.28x |
| val | q01 | 362.0 | 1.18x | 1.04x | 1.03x | 1.01x | 1.03x | 1.01x | 1.00x | 1.01x |
| val | q11 | 49.9 | 0.99x | 0.98x | 1.02x | 1.02x | 1.00x | 0.97x | 1.00x | 0.97x |
| val | q21 | 867.6 | 0.97x | 0.99x | 1.06x | 0.98x | 0.96x | 0.96x | 0.98x | 1.21x |
| test | q06 | 70.9 | 0.86x | 1.00x | 0.98x | 0.97x | 0.97x | 0.97x | 0.99x | 1.00x |
| test | q10 | 494.6 | 0.96x | 0.99x | 1.04x | 1.03x | 0.99x | 0.97x | 0.99x | 1.01x |
| test | q12 | 191.4 | 0.99x | 0.98x | 1.07x | 1.03x | 1.00x | 1.01x | 0.99x | 1.03x |
| test | q15 | 125.2 | 0.99x | 1.00x | 1.06x | 1.49x | 1.01x | 1.03x | 1.04x | 1.05x |
| test | q20 | 174.1 | 1.01x | 1.02x | 1.07x | 0.99x | 0.99x | 1.02x | 1.02x | 1.06x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
