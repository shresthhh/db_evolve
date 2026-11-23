# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 171.8 ms, total 751 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q21 | 708.9 | 94.5% |
| q02 | 41.6 | 5.5% |

## Plans with operator timings (slowest templates)

### q21.m0

```sql
SELECT s_name, count(*) AS numwait FROM supplier, lineitem l1, orders, nation WHERE s_suppkey = l1.l_suppkey AND o_orderkey = l1.l_orderkey AND o_orderstatus = 'F' AND l1.l_receiptdate > l1.l_commitdate AND EXISTS (SELECT * FROM lineitem l2 WHERE l2.l_orderkey = l1.l_orderkey AND l2.l_suppkey <> l1.l_suppkey) AND NOT EXISTS (SELECT * FROM lineitem l3 WHERE l3.l_orderkey = l1.l_orderkey AND l3.l_suppkey <> l1.l_suppkey AND l3.l_receiptdate > l3.l_commitdate) AND s_nationkey = n_nationkey AND n_name = 'JAPAN' GROUP BY s_name ORDER BY numwait DESC, s_name LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││               Total Time: 1.01s              ││
│└──────────────────────────────────────────────┘│
└────────────────────────────────────────────────┘
┌─────────────────┐
│      QUERY      │
└────────┬────────┘
┌────────┴────────┐
│ EXPLAIN_ANALYZE │
│    ──────────   │
│                 │
│      0 rows     │
│      0.00s      │
└────────┬────────┘
┌────────┴────────┐
│      TOP_N      │
│    ──────────   │
│     Top: 100    │
│                 │
│    Order By:    │
│count_star() DESC│
│ "tpch-main-sf10"│
│  .main.supplier │
│   .s_name ASC   │
│                 │
│                 │
│                 │
│     100 rows    │
│      0.00s      │
└────────┬────────┘
┌────────┴────────┐
│  HASH_GROUP_BY  │
│    ──────────   │
│    Groups: #0   │
│                 │
│   Aggregates:   │
│   count_star()  │
│                 │
│                 │
│                 │
│    4,009 rows   │
│      0.02s      │
└────────┬────────┘
┌────────┴────────┐
│    PROJECTION   │
│    ──────────   │
│      s_name     │
│                 │
│                 │
│                 │
│   40,074 rows   │
│      0.00s      │
└────────┬────────┘
┌────────┴────────┐
│ LEFT_DELIM_JOIN │
│    ──────────   │
│    Join Type:   │
│       ANTI      │
│                 │
│   Conditions:   │
│ l_suppkey IS NOT│
│   DISTINCT FROM │
│     l_suppkey   │
│  l_orderkey IS  │
│   NOT DISTINCT  ├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────┐
│  FROM l_orderkey│                                                                                                                                              │                                                        │
│                 │                                                                                                                                              │                                                        │
│   Delim Index:  │                                                                                                                                              │                                                        │
│        2        │                                                                                                                                              │                                                        │
│                 │                                                                                                                                              │                                                        │
│                 │                                                                                                                                              │                                                        │
│                 │                                                                                                                                              │                                                        │
│      0 rows     │                                                                                                                                              │                                                        │
│      0.10s      │                                                                                                                                              │                                                        │
└────────┬────────┘                                                                                                                                              │                                                        │
┌────────┴────────┐                                                                                                                                     ┌────────┴────────┐                                      ┌────────┴────────┐
│ RIGHT_DELIM_JOIN│                                                                                                                                     │    HASH_JOIN    │                                      │  HASH_GROUP_BY  │
│    ──────────   │                                                                                                                                     │    ──────────   │                                      │    ──────────   │
│    Join Type:   │                                                                                                                                     │    Join Type:   │                                      │     Groups:     │
│    RIGHT_SEMI   │                                                                                                                                     │       ANTI      │                                      │        #1       │
│                 │                                                                                                                                     │                 │                                      │        #0       │
│   Conditions:   │                                                                                                                                     │   Conditions:   │                                      │                 │
│ l_suppkey IS NOT│                                                                                                                                     │ l_suppkey IS NOT│                                      │                 │
│   DISTINCT FROM │                                                                                                                                     │   DISTINCT FROM │                                      │                 │
│     l_suppkey   │                                                                                                                                     │     l_suppkey   │                                      │                 │
│  l_orderkey IS  │                                                                                                                                     │  l_orderkey IS  │                                      │      0.03s      │
│   NOT DISTINCT  ├──────────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────┐         │   NOT DISTINCT  ├─────────┐                            │                 │
│  FROM l_orderkey│                                                                  │                                                        │         │  FROM l_orderkey│         │                            │                 │
│                 │                                                                  │                                                        │         │                 │         │                            │                 │
│   Delim Index:  │                                                                  │                                                        │         │                 │         │                            │                 │
│        1        │                                                                  │                                                        │         │                 │         │                            │                 │
│                 │                                                                  │                                                        │         │                 │         │                            │                 │
│                 │                                                                  │                                                        │         │      0.30s      │         │                            │                 │
│                 │                                                                  │                                                        │         │                 │         │                            │                 │
│      0 rows     │                                                                  │                                                        │         │   40,074 rows   │         │                            │   708,431 rows  │
│      0.32s      │                                                                  │                                                        │         │     (0.30s)     │         │                            │     (0.03s)     │
└────────┬────────┘                                                                  │                                                        │         └────────┬────────┘         │                            └─────────────────┘
┌────────┴────────┐                                                         ┌────────┴────────┐                                      ┌────────┴────────┐┌────────┴────────┐┌────────┴────────┐
│    HASH_JOIN    │                                                         │    HASH_JOIN    │                                      │  HASH_GROUP_BY  ││ COLUMN_DATA_SCAN││    PROJECTION   │
│    ──────────   │                                                         │    ──────────   │                                      │    ──────────   ││                 ││    ──────────   │
│    Join Type:   │                                                         │    Join Type:   │                                      │     Groups:     ││                 ││    l_suppkey    │
│      INNER      │                                                         │    RIGHT_SEMI   │                                      │        #2       ││      0.00s      ││    l_orderkey   │
│                 │                                                         │                 │                                     
... (truncated)
```

### q02.m0

```sql
SELECT s_acctbal, s_name, n_name, p_partkey, p_mfgr, s_address, s_phone, s_comment FROM part, supplier, partsupp, nation, region WHERE p_partkey = ps_partkey AND s_suppkey = ps_suppkey AND p_size = 1 AND p_type LIKE '%STEEL' AND s_nationkey = n_nationkey AND n_regionkey = r_regionkey AND r_name = 'AMERICA' AND ps_supplycost = ( SELECT min(ps_supplycost) FROM partsupp, supplier, nation, region WHERE p_partkey = ps_partkey AND s_suppkey = ps_suppkey AND s_nationkey = n_nationkey AND n_regionkey = r_regionkey AND r_name = 'AMERICA') ORDER BY s_acctbal DESC, n_name, s_name, p_partkey LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.0499s             ││
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
│           TOP_N           │
│    ────────────────────   │
│          Top: 100         │
│                           │
│         Order By:         │
│   "tpch-main-sf10".main   │
│  .supplier.s_acctbal DESC │
│   "tpch-main-sf10".main   │
│     .nation.n_name ASC    │
│   "tpch-main-sf10".main   │
│    .supplier.s_name ASC   │
│ "tpch-main-sf10".main.part│
│       .p_partkey ASC      │
│                           │
│                           │
│                           │
│          100 rows         │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│         s_acctbal         │
│           s_name          │
│           n_name          │
│         p_partkey         │
│           p_mfgr          │
│         s_address         │
│          s_phone          │
│         s_comment         │
│                           │
│                           │
│                           │
│         4,816 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #1            │
│             #2            │
│             #3            │
│             #4            │
│             #5            │
│             #6            │
│             #7            │
│             #8            │
│                           │
│                           │
│                           │
│         4,816 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           FILTER          │
│    ────────────────────   │
│ (ps_supplycost = SUBQUERY)│
│                           │
│                           │
│                           │
│         4,816 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│             #1            │
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
│         6,460 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           WINDOW          │
│    ────────────────────   │
│        Projections:       │
│  min(ps_supplycost) OVER  │
│  (PARTITION BY p_partkey  │
│   ROWS BETWEEN UNBOUNDED  │
│   PRECEDING AND UNBOUNDED │
│         FOLLOWING)        │
│                           │
│                           │
│                           │
│         6,460 rows        │
│           0.02s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: INNER     │
│                           │
│        Conditions:        │
│   ps_suppkey = s_suppkey  ├───────────────────────────────────────────┐
│                           │                                           │
│                           │                                           │
│                           │                                           │
│         6,460 rows        │                                           │
│           0.01s           │                                           │
└─────────────┬─────────────┘                                           │
┌─────────────┴─────────────┐                             ┌─────────────┴─────────────┐
│         HASH_JOIN         │                             │         HASH_JOIN         │
│    ────────────────────   │                             │    ────────────────────   │
│      Join Type: INNER     │                             │      Join Type: INNER     │
│                           │                             │                           │
│        Conditions:        │                             │        Conditions:        │
│   ps_partkey = p_partkey  ├──────────────┐              │ s_nationkey = n_nationkey ├──────────────┐
│                           │              │              │                           │              │
│                           │              │              │                           │              │
│                           │              │              │                           │              │
│        32,244 rows        │              │              │        20,051 rows        │              │
│           0.03s           │              │              │           0.00s           │              │
└─────────────┬─────────────┘              │              └─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         TABLE_SCAN        ││         TABLE_SCAN        ││         HASH_JOIN         │
│    ────────────────────   ││    ────────────────────   ││    ────────────────────   ││    ────────────────────   │
│           Table:          ││           Table:          ││           Table:          ││      Join Type: INNER     │
│   "tpch-main-sf10".main   ││ "tpch-main-sf10".main.part││   "tpch-main-sf10".main   ││                           │
│         .partsupp         ││                           ││         .supplier         ││        Conditions:        │
│                           ││   Type: Sequential Scan   ││                           ││ n_regionkey = r_regionkey │
│   Type: Sequential Scan   ││                           ││   Type: Sequential Scan   ││                           │
│                           ││        Projections:       ││                           ││                           │
│        Projections:       ││         p_partkey         ││        Projections:       ││                           │
│         ps_partkey        ││           p_mfgr          ││         s_suppkey         ││                           │
│         ps_suppkey        ││                           ││        s_nationkey        ││           0.00s           │
│       ps_supplycost       ││          Filters:         ││         s_acctbal         ││                           │
│                           ││          p_size=1         ││           s_name          ││                           │
│      Dynamic Filters:     ││  suffix(p_type, 'STEEL')  ││         s_address         ││                           │
│ optional: ps_partkey>=124 ││                           ││          s_phone          ││                           ├──────────────┐
│  AND optional: ps_partkey<││                           ││         s_comment         ││                           │              │
│   =1999889 AND optional:  ││                           ││                           ││                           │              │
│      ps_partkey IN BF     ││                           ││      Dynamic Filters:     ││                           │              │
│        (p_partkey)        ││           0.04s           ││ optional: s_nationkey IN  ││                           │              │
│  optional: ps_suppkey>=1  ││                           ││   (1, 2, 3, 17, 24) AND   ││                           │              │
│  AND optional: ps_suppkey<││                           ││  optional: s_nationkey>=1 ││                           │              │
│           =99999          ││                           ││  AND optional: s_nationkey││                           │              │
│                           ││                           ││            <=24           ││                           │              │
│                           ││                           ││                           ││                           │              │
│                           ││                           ││                           ││                           │              │
│                           ││                           ││                           ││                           │              │
│           0.17s           ││         8,061 rows        ││        96,066 rows        ││           5 rows          │              │
│          (0.17s)          ││          (0.04s)          ││           0.03s           ││          (0.00s)          │              │
└───────────────────────────┘└───────────────────────────┘└───────────────────────────┘└─────────────┬─────────────┘              │
                                                                                       ┌─────────────┴─────────────┐┌─────────────┴─────────────┐
                                                                                       │         TABLE_SCAN        ││         TABLE_SCAN        │
                                                                                       │    ────────────────────   ││    ────────────────────   │
                                                                                       │           Table:          ││           Table:          │
                                                                                       │   "tpch-main-sf10".main   ││   "tpch-main-sf10".main   │
                                                                                       │     
... (truncated)
```
