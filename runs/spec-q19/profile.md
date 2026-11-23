# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 145.2 ms, total 145 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q19 | 145.2 | 100.0% |

## Plans with operator timings (slowest templates)

### q19.m0

```sql
SELECT sum(l_extendedprice * (1 - l_discount)) AS revenue FROM lineitem, part WHERE (p_partkey = l_partkey AND p_brand = 'Brand#45' AND p_container IN ('SM CASE', 'SM BOX', 'SM PACK', 'SM PKG') AND l_quantity >= 9 AND l_quantity <= 9 + 10 AND p_size BETWEEN 1 AND 5 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON') OR (p_partkey = l_partkey AND p_brand = 'Brand#33' AND p_container IN ('MED BAG', 'MED BOX', 'MED PKG', 'MED PACK') AND l_quantity >= 20 AND l_quantity <= 20 + 10 AND p_size BETWEEN 1 AND 10 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON') OR (p_partkey = l_partkey AND p_brand = 'Brand#41' AND p_container IN ('LG CASE', 'LG BOX', 'LG PACK', 'LG PKG') AND l_quantity >= 23 AND l_quantity <= 23 + 10 AND p_size BETWEEN 1 AND 15 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON')
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.426s              ││
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
│           0.01s           │              │
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
│          (0.00s)          ││           0.06s           │
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
│          (0.10s)          ││           0.05s           │
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
│           3.01s           │
└───────────────────────────┘
```
