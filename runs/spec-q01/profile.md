# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 298.3 ms, total 298 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q01 | 298.3 | 100.0% |

## Plans with operator timings (slowest templates)

### q01.m0

```sql
SELECT l_returnflag, l_linestatus, sum(l_quantity) AS sum_qty, sum(l_extendedprice) AS sum_base_price, sum(l_extendedprice * (1 - l_discount)) AS sum_disc_price, sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS sum_charge, avg(l_quantity) AS avg_qty, avg(l_extendedprice) AS avg_price, avg(l_discount) AS avg_disc, count(*) AS count_order FROM lineitem WHERE l_shipdate <= DATE '1998-12-01' - INTERVAL '108' DAY GROUP BY l_returnflag, l_linestatus ORDER BY l_returnflag, l_linestatus
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.480s              ││
│└──────────────────────────────────────────────┘│
└────────────────────────────────────────────────┘
┌───────────────────────────┐
│           QUERY           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│      EXPLAIN_ANALYZE      │
│    ────────────────────   │
│                           │
│           0 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_strin│
│           g(#0)           │
│__internal_decompress_strin│
│           g(#1)           │
│             #2            │
│             #3            │
│             #4            │
│             #5            │
│             #6            │
│             #7            │
│             #8            │
│             #9            │
│                           │
│                           │
│                           │
│           4 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          ORDER_BY         │
│    ────────────────────   │
│   "tpch-main-sf10".main   │
│ .lineitem.l_returnflag ASC│
│   "tpch-main-sf10".main   │
│ .lineitem.l_linestatus ASC│
│                           │
│                           │
│                           │
│           4 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_string_│
│        utinyint(#0)       │
│__internal_compress_string_│
│        utinyint(#1)       │
│             #2            │
│             #3            │
│             #4            │
│             #5            │
│             #6            │
│             #7            │
│             #8            │
│             #9            │
│                           │
│                           │
│                           │
│           4 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_strin│
│           g(#0)           │
│__internal_decompress_strin│
│           g(#1)           │
│             #2            │
│             #3            │
│             #4            │
│             #5            │
│             #6            │
│             #7            │
│             #8            │
│             #9            │
│                           │
│                           │
│                           │
│           4 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│   PERFECT_HASH_GROUP_BY   │
│    ────────────────────   │
│          Groups:          │
│             #0            │
│             #1            │
│                           │
│        Aggregates:        │
│    sum_no_overflow(#2)    │
│    sum_no_overflow(#3)    │
│    sum_no_overflow(#4)    │
│    sum_no_overflow(#5)    │
│          avg(#6)          │
│          avg(#7)          │
│          avg(#8)          │
│        count_star()       │
│                           │
│                           │
│                           │
│           4 rows          │
│           1.13s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│        l_returnflag       │
│        l_linestatus       │
│         l_quantity        │
│      l_extendedprice      │
│             #4            │
│   (#4 * (1.00 + l_tax))   │
│         l_quantity        │
│      l_extendedprice      │
│         l_discount        │
│                           │
│                           │
│                           │
│      58,773,499 rows      │
│           0.18s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_string_│
│        utinyint(#0)       │
│__internal_compress_string_│
│        utinyint(#1)       │
│             #2            │
│             #3            │
│             #4            │
│             #5            │
│             #6            │
│                           │
│                           │
│                           │
│      58,773,499 rows      │
│           0.04s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│        l_returnflag       │
│        l_linestatus       │
│         l_quantity        │
│      l_extendedprice      │
│ (l_extendedprice * (1.00 -│
│        l_discount))       │
│           l_tax           │
│         l_discount        │
│                           │
│                           │
│                           │
│      58,773,499 rows      │
│           0.19s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         TABLE_SCAN        │
│    ────────────────────   │
│           Table:          │
│   "tpch-main-sf10".main   │
│         .lineitem         │
│                           │
│   Type: Sequential Scan   │
│                           │
│        Projections:       │
│        l_returnflag       │
│        l_linestatus       │
│         l_quantity        │
│      l_extendedprice      │
│         l_discount        │
│           l_tax           │
│                           │
│          Filters:         │
│ l_shipdate<='1998-08-15': │
│           :DATE           │
│                           │
│                           │
│                           │
│      58,773,499 rows      │
│           2.09s           │
└───────────────────────────┘
```
