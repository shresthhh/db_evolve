# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 205.9 ms, total 434 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q01 | 286.3 | 65.9% |
| q19 | 148.1 | 34.1% |

## Plans with operator timings (slowest templates)

### q01.m0

```sql
SELECT l_returnflag, l_linestatus, sum(l_quantity) AS sum_qty, sum(l_extendedprice) AS sum_base_price, sum(l_extendedprice * (1 - l_discount)) AS sum_disc_price, sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS sum_charge, avg(l_quantity) AS avg_qty, avg(l_extendedprice) AS avg_price, avg(l_discount) AS avg_disc, count(*) AS count_order FROM lineitem WHERE l_shipdate <= DATE '1998-12-01' - INTERVAL '108' DAY GROUP BY l_returnflag, l_linestatus ORDER BY l_returnflag, l_linestatus
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.476s              ││
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
│           1.10s           │
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
│           0.17s           │
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
│           2.12s           │
└───────────────────────────┘
```

### q19.m0

```sql
SELECT sum(l_extendedprice * (1 - l_discount)) AS revenue FROM lineitem, part WHERE (p_partkey = l_partkey AND p_brand = 'Brand#45' AND p_container IN ('SM CASE', 'SM BOX', 'SM PACK', 'SM PKG') AND l_quantity >= 9 AND l_quantity <= 9 + 10 AND p_size BETWEEN 1 AND 5 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON') OR (p_partkey = l_partkey AND p_brand = 'Brand#33' AND p_container IN ('MED BAG', 'MED BOX', 'MED PKG', 'MED PACK') AND l_quantity >= 20 AND l_quantity <= 20 + 10 AND p_size BETWEEN 1 AND 10 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON') OR (p_partkey = l_partkey AND p_brand = 'Brand#41' AND p_container IN ('LG CASE', 'LG BOX', 'LG PACK', 'LG PKG') AND l_quantity >= 23 AND l_quantity <= 23 + 10 AND p_size BETWEEN 1 AND 15 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON')
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.276s              ││
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
│    UNGROUPED_AGGREGATE    │
│    ────────────────────   │
│    Aggregates: sum(#0)    │
│                           │
│                           │
│                           │
│           1 row           │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│ (l_extendedprice * (1.00 -│
│        l_discount))       │
│                           │
│                           │
│                           │
│         1,170 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #1            │
│             #2            │
│                           │
│                           │
│                           │
│         1,170 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           FILTER          │
│    ────────────────────   │
│ (((l_quantity >= 9.00) AND│
│  (l_quantity <= 19.00) AND│
│     (p_size <= 5) AND     │
│ (p_brand = 'Brand#45') AND│
│  ((p_container = 'SM CASE'│
│  ) OR (p_container = 'SM  │
│  BOX') OR (p_container =  │
│ 'SM PACK') OR (p_container│
│     = 'SM PKG'))) OR (    │
│ (l_quantity >= 20.00) AND │
│ (l_quantity <= 30.00) AND │
│    (p_size <= 10) AND     │
│ (p_brand = 'Brand#33') AND│
│  ((p_container = 'MED BAG'│
│  ) OR (p_container = 'MED │
│  BOX') OR (p_container =  │
│ 'MED PKG') OR (p_container│
│    = 'MED PACK'))) OR (   │
│ (l_quantity >= 23.00) AND │
│ (l_quantity <= 33.00) AND │
│    (p_size <= 15) AND     │
│ (p_brand = 'Brand#41') AND│
│  ((p_container = 'LG CASE'│
│  ) OR (p_container = 'LG  │
│  BOX') OR (p_container =  │
│ 'LG PACK') OR (p_container│
│       = 'LG PKG'))))      │
│                           │
│                           │
│                           │
│         1,170 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: INNER     │
│                           │
│        Conditions:        │
│   l_partkey = p_partkey   ├──────────────┐
│                           │              │
│                           │              │
│                           │              │
│         2,672 rows        │              │
│           0.00s           │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         PROJECTION        ││           FILTER          │
│    ────────────────────   ││    ────────────────────   │
│             #0            ││   (((p_size <= 5) AND (   │
│             #1            ││ (p_brand = 'Brand#45') AND│
│             #3            ││  ((p_container = 'SM CASE'│
│             #4            ││  ) OR (p_container = 'SM  │
│                           ││  BOX') OR (p_container =  │
│                           ││ 'SM PACK') OR (p_container│
│                           ││     = 'SM PKG')))) OR (   │
│                           ││    (p_size <= 10) AND (   │
│           0.00s           ││ (p_brand = 'Brand#33') AND│
│                           ││  ((p_container = 'MED BAG'│
│                           ││  ) OR (p_container = 'MED │
│                           ││  BOX') OR (p_container =  │
│                           ││ 'MED PKG') OR (p_container│
│                           ││    = 'MED PACK')))) OR (  │
│                           ││    (p_size <= 15) AND (   │
│                           ││ (p_brand = 'Brand#41') AND│
│                           ││  ((p_container = 'LG CASE'│
│                           ││  ) OR (p_container = 'LG  │
│                           ││  BOX') OR (p_container =  │
│                           ││ 'LG PACK') OR (p_container│
│                           ││       = 'LG PKG')))))     │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│        11,797 rows        ││         4,862 rows        │
│          (0.00s)          ││           0.07s           │
└─────────────┬─────────────┘└─────────────┬─────────────┘
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│           FILTER          ││         TABLE_SCAN        │
│    ────────────────────   ││    ────────────────────   │
│ ((l_shipmode = 'AIR') OR  ││           Table:          │
│ (l_shipmode = 'AIR REG')) ││ "tpch-main-sf10".main.part│
│                           ││                           │
│                           ││   Type: Sequential Scan   │
│                           ││                           │
│                           ││        Projections:       │
│           0.10s           ││         p_partkey         │
│                           ││          p_brand          │
│                           ││        p_container        │
│                           ││           p_size          │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│        11,797 rows        ││       2,000,000 rows      │
│          (0.10s)          ││           0.04s           │
└─────────────┬─────────────┘└───────────────────────────┘
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
│         l_partkey         │
│         l_quantity        │
│         l_shipmode        │
│      l_extendedprice      │
│         l_discount        │
│                           │
│          Filters:         │
│ (((l_quantity >= 9.00) AND│
│  (l_quantity <= 19.00)) OR│
│   ((l_quantity >= 20.00)  │
│  AND (l_quantity <= 30.00)│
│ ) OR ((l_quantity >= 23.00│
│ ) AND (l_quantity <= 33.00│
│            )))            │
│ optional: l_shipmode IN ( │
│   'AIR', 'AIR REG') AND   │
│  optional: l_shipmode IN (│
│     'AIR', 'AIR REG')     │
│ l_shipinstruct='DELIVER IN│
│           PERSON'         │
│                           │
│      Dynamic Filters:     │
│ optional: l_partkey>=1165 │
│  AND optional: l_partkey< │
│   =1999799 AND optional:  │
│ l_partkey IN BF(p_partkey)│
│                           │
│                           │
│                           │
│        82,782 rows        │
│           1.89s           │
└───────────────────────────┘
```
