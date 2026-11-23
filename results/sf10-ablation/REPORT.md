# Release report: tpch (SF 10.0, 8 threads)

Generated 2026-11-19T00:57:09-05:00. Times are hot-run medians; a split's score is the geometric mean of its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.

## Geomean latency (ms) and speedup by split

| Version | Commit | train (visible) | validation (hidden) | test (held out) | Wrong results |
| --- | --- | ---: | ---: | ---: | ---: |
| v0 | `069cc9f9b5` | 272.1 (1.000x) | 243.4 (1.000x) | 165.5 (1.000x) | 0 |
| only-E0008 | `8beba2de13` | 261.4 (1.041x) | 247.2 (0.984x) | 171.3 (0.966x) | 0 |
| v3-minus-E0008 | `0fc2f6c9bd` | 245.3 (1.109x) | 216.8 (1.123x) | 163.2 (1.014x) | 0 |
| only-E0009 | `fc3ca7db6d` | 270.6 (1.006x) | 244.6 (0.995x) | 165.4 (1.001x) | 0 |
| v3-minus-E0009 | `dac10b70ca` | 235.1 (1.157x) | 214.8 (1.133x) | 165.5 (1.000x) | 0 |
| only-E0010 | `5411635cff` | 258.4 (1.053x) | 245.0 (0.994x) | 168.0 (0.985x) | 0 |
| v3-minus-E0010 | `9c967d5f82` | 243.1 (1.119x) | 215.0 (1.132x) | 162.7 (1.018x) | 0 |
| only-E0011 | `f7fd393778` | 263.0 (1.035x) | 217.8 (1.117x) | 168.8 (0.981x) | 0 |
| v3-minus-E0012 | `57bc88de5e` | 238.7 (1.140x) | 218.6 (1.114x) | 164.6 (1.005x) | 0 |
| v3 | `b6929da26e` | 238.8 (1.140x) | 216.5 (1.124x) | 169.8 (0.975x) | 0 |

Measurement noise in this report (v0 timed twice, as itself and as a control): train ±0.8%, val ±0.8%, test ±3.3%. Differences smaller than this are not evidence.

## Speedup vs v0 by template

| Split | Template | v0 ms | only-E0008 | v3-minus-E0008 | only-E0009 | v3-minus-E0009 | only-E0010 | v3-minus-E0010 | only-E0011 | v3-minus-E0012 | v3 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | q02 | 78.4 | 0.97x | 0.96x | 0.95x | 0.90x | 0.93x | 0.92x | 0.90x | 0.91x | 0.98x |
| train | q03 | 256.9 | 1.09x | 1.09x | 1.09x | 1.09x | 1.09x | 1.08x | 1.06x | 1.04x | 0.98x |
| train | q04 | 273.0 | 0.98x | 1.32x | 1.00x | 1.31x | 1.01x | 1.36x | 1.34x | 1.32x | 1.25x |
| train | q05 | 256.3 | 0.99x | 1.00x | 0.98x | 1.00x | 1.00x | 1.01x | 1.00x | 0.98x | 0.96x |
| train | q07 | 187.5 | 1.02x | 1.02x | 0.99x | 1.04x | 1.02x | 1.01x | 1.00x | 1.01x | 1.02x |
| train | q08 | 213.7 | 1.01x | 1.00x | 0.98x | 1.02x | 0.99x | 1.00x | 1.00x | 0.99x | 0.98x |
| train | q09 | 1127.9 | 1.58x | 1.01x | 0.99x | 1.58x | 1.03x | 1.97x | 0.94x | 1.95x | 1.93x |
| train | q13 | 776.1 | 1.02x | 1.02x | 1.02x | 1.04x | 1.02x | 1.04x | 0.98x | 1.00x | 1.01x |
| train | q14 | 154.3 | 1.00x | 1.00x | 1.03x | 1.03x | 0.96x | 1.02x | 0.99x | 0.99x | 0.99x |
| train | q16 | 191.7 | 1.04x | 1.00x | 1.03x | 1.04x | 1.01x | 1.05x | 1.03x | 1.03x | 1.00x |
| train | q17 | 209.4 | 1.01x | 0.99x | 1.02x | 1.03x | 1.03x | 1.02x | 1.02x | 1.03x | 1.00x |
| train | q18 | 660.8 | 0.99x | 1.01x | 1.01x | 1.04x | 1.00x | 1.02x | 1.01x | 1.00x | 1.00x |
| train | q19 | 347.4 | 1.02x | 2.01x | 1.03x | 2.02x | 2.00x | 1.05x | 1.03x | 2.02x | 1.98x |
| train | q22 | 174.0 | 0.96x | 1.48x | 0.97x | 1.49x | 0.97x | 1.48x | 1.26x | 1.24x | 1.44x |
| val | q01 | 341.7 | 0.97x | 0.98x | 0.98x | 0.99x | 0.99x | 0.99x | 1.01x | 0.98x | 0.99x |
| val | q11 | 48.3 | 0.98x | 1.01x | 0.99x | 1.02x | 0.99x | 1.00x | 0.99x | 0.99x | 1.01x |
| val | q21 | 874.7 | 1.00x | 1.43x | 1.02x | 1.44x | 1.00x | 1.47x | 1.40x | 1.43x | 1.42x |
| test | q06 | 70.0 | 0.98x | 1.00x | 0.98x | 1.00x | 0.98x | 1.01x | 0.99x | 1.00x | 0.97x |
| test | q10 | 479.9 | 0.92x | 1.00x | 0.98x | 0.99x | 0.98x | 1.00x | 0.97x | 0.99x | 0.94x |
| test | q12 | 186.8 | 0.97x | 1.01x | 0.99x | 1.00x | 1.01x | 1.02x | 0.97x | 1.02x | 0.97x |
| test | q15 | 119.3 | 0.99x | 1.01x | 1.00x | 1.02x | 0.97x | 1.01x | 0.99x | 0.99x | 0.97x |
| test | q20 | 166.0 | 0.98x | 1.05x | 1.05x | 1.00x | 0.99x | 1.06x | 0.98x | 1.03x | 1.03x |

The test split is held out: agents never see its queries, and it is not used to accept or reject changes. A gain on train that does not appear on test is overfitting.
