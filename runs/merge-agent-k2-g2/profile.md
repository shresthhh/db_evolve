# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 380.5 ms, total 1340 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q21 | 694.7 | 51.8% |
| q13 | 480.2 | 35.8% |
| q16 | 165.1 | 12.3% |

## Plans with operator timings (slowest templates)

### q21.m0

```sql
SELECT s_name, count(*) AS numwait FROM supplier, lineitem l1, orders, nation WHERE s_suppkey = l1.l_suppkey AND o_orderkey = l1.l_orderkey AND o_orderstatus = 'F' AND l1.l_receiptdate > l1.l_commitdate AND EXISTS (SELECT * FROM lineitem l2 WHERE l2.l_orderkey = l1.l_orderkey AND l2.l_suppkey <> l1.l_suppkey) AND NOT EXISTS (SELECT * FROM lineitem l3 WHERE l3.l_orderkey = l1.l_orderkey AND l3.l_suppkey <> l1.l_suppkey AND l3.l_receiptdate > l3.l_commitdate) AND s_nationkey = n_nationkey AND n_name = 'JAPAN' GROUP BY s_name ORDER BY numwait DESC, s_name LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.979s              ││
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
│      0.01s      │
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
│      0.09s      │                                                                                                                                              │                                                        │
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
│                 │                                                                  │                                                        │         │      0.26s      │         │                            │                 │
│                 │                                                                  │                                                        │         │                 │         │                            │                 │
│      0 rows     │                                                                  │                                                        │         │   40,074 rows   │         │                            │   708,431 rows  │
│      0.36s      │                                                                  │                                                        │         │     (0.26s)     │         │                            │     (0.03s)     │
└────────┬────────┘                                                                  │                                                        │         └────────┬────────┘         │                            └─────────────────┘
┌────────┴────────┐                                                         ┌────────┴────────┐                                      ┌────────┴────────┐┌────────┴────────┐┌────────┴────────┐
│    HASH_JOIN    │                                                         │    HASH_JOIN    │                                      │  HASH_GROUP_BY  ││ COLUMN_DATA_SCAN││    PROJECTION   │
│    ──────────   │                                                         │    ──────────   │                                      │    ──────────   ││                 ││    ──────────   │
│    Join Type:   │                                                         │    Join Type:   │                                      │     Groups:     ││                 ││    l_suppkey    │
│      INNER      │                                                         │    RIGHT_SEMI   │                                      │        #2       ││      0.00s      ││    l_orderkey   │
│                 │                                                         │                 │                                     
... (truncated)
```

### q13.m0

```sql
SELECT c_count, count(*) AS custdist FROM ( SELECT c_custkey, count(o_orderkey) FROM customer LEFT OUTER JOIN orders ON c_custkey = o_custkey AND o_comment NOT LIKE '%unusual%packages%' GROUP BY c_custkey) AS c_orders (c_custkey, c_count) GROUP BY c_count ORDER BY custdist DESC, c_count DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.549s              ││
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
│          ORDER_BY         │
│    ────────────────────   │
│     count_star() DESC     │
│   c_orders.c_count DESC   │
│                           │
│                           │
│                           │
│          45 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│         Groups: #0        │
│                           │
│        Aggregates:        │
│        count_star()       │
│                           │
│                           │
│                           │
│          45 rows          │
│           0.06s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          c_count          │
│                           │
│                           │
│                           │
│       1,500,000 rows      │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│     count(o_orderkey)     │
│                           │
│                           │
│                           │
│       1,500,000 rows      │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_integ│
│     ral_bigint(#0, 1)     │
│             #1            │
│                           │
│                           │
│                           │
│       1,500,000 rows      │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│   PERFECT_HASH_GROUP_BY   │
│    ────────────────────   │
│         Groups: #0        │
│   Aggregates: count(#1)   │
│                           │
│                           │
│                           │
│       1,500,000 rows      │
│           0.43s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│         c_custkey         │
│         o_orderkey        │
│                           │
│                           │
│                           │
│      15,333,290 rows      │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│__internal_compress_integra│
│     l_uinteger(#1, 1)     │
│                           │
│                           │
│                           │
│      15,333,290 rows      │
│           0.01s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│__internal_decompress_integ│
│     ral_bigint(#1, 1)     │
│                           │
│                           │
│                           │
│      15,333,290 rows      │
│           0.15s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: RIGHT     │
│                           │
│        Conditions:        │
│   o_custkey = c_custkey   ├──────────────┐
│                           │              │
│                           │              │
│                           │              │
│      15,333,290 rows      │              │
│           0.16s           │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         PROJECTION        ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│__internal_compress_integra││__internal_compress_integra│
│     l_uinteger(#0, 1)     ││     l_uinteger(#0, 1)     │
│             #1            ││                           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│      14,833,270 rows      ││           0.00s           │
│           0.03s           ││          (0.00s)          │
└─────────────┬─────────────┘└─────────────┬─────────────┘
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         TABLE_SCAN        │
│    ────────────────────   ││    ────────────────────   │
│           Table:          ││           Table:          │
│   "tpch-main-sf10".main   ││   "tpch-main-sf10".main   │
│          .orders          ││         .customer         │
│                           ││                           │
│   Type: Sequential Scan   ││   Type: Sequential Scan   │
│                           ││                           │
│        Projections:       ││        Projections:       │
│         o_custkey         ││         c_custkey         │
│         o_orderkey        ││                           │
│                           ││                           │
│          Filters:         ││                           │
│  (o_comment !~~ '%unusual ││                           │
│        %packages%')       ││           0.01s           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│      14,833,270 rows      ││       1,500,000 rows      │
│           2.12s           ││          (0.01s)          │
└───────────────────────────┘└───────────────────────────┘
```

### q16.m0

```sql
SELECT p_brand, p_type, p_size, count(DISTINCT ps_suppkey) AS supplier_cnt FROM partsupp, part WHERE p_partkey = ps_partkey AND p_brand <> 'Brand#51' AND p_type NOT LIKE 'MEDIUM PLATED%' AND p_size IN (29, 2, 23, 11, 13, 1, 46, 40) AND ps_suppkey NOT IN (SELECT s_suppkey FROM supplier WHERE s_comment LIKE '%Customer%Complaints%') GROUP BY p_brand, p_type, p_size ORDER BY supplier_cnt DESC, p_brand, p_type, p_size
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.169s              ││
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
│             #1            │
│__internal_decompress_integ│
│     ral_integer(#2, 1)    │
│             #3            │
│                           │
│                           │
│                           │
│        27,839 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          ORDER_BY         │
│    ────────────────────   │
│ count(DISTINCT "tpch-main │
│    -sf10".main.partsupp   │
│     .ps_suppkey) DESC     │
│ "tpch-main-sf10".main.part│
│        .p_brand ASC       │
│ "tpch-main-sf10".main.part│
│        .p_type ASC        │
│ "tpch-main-sf10".main.part│
│        .p_size ASC        │
│                           │
│                           │
│                           │
│        27,839 rows        │
│           0.01s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_string_│
│        uhugeint(#0)       │
│             #1            │
│__internal_compress_integra│
│     l_utinyint(#2, 1)     │
│             #3            │
│                           │
│                           │
│                           │
│        27,839 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_strin│
│           g(#0)           │
│             #1            │
│__internal_decompress_integ│
│     ral_integer(#2, 1)    │
│             #3            │
│                           │
│                           │
│                           │
│        27,839 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│          Groups:          │
│             #0            │
│             #1            │
│             #2            │
│                           │
│        Aggregates:        │
│     count(DISTINCT #3)    │
│                           │
│                           │
│                           │
│        27,839 rows        │
│           0.42s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          p_brand          │
│           p_type          │
│           p_size          │
│         ps_suppkey        │
│                           │
│                           │
│                           │
│       1,184,892 rows      │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│__internal_compress_string_│
│        uhugeint(#1)       │
│             #2            │
│__internal_compress_integra│
│     l_utinyint(#3, 1)     │
│                           │
│                           │
│                           │
│       1,184,892 rows      │
│           0.02s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│             #1            │
│             #2            │
│             #3            │
│                           │
│                           │
│                           │
│       1,184,892 rows      │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           FILTER          │
│    ────────────────────   │
│       (NOT SUBQUERY)      │
│                           │
│                           │
│                           │
│       1,184,892 rows      │
│           0.01s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: MARK      │
│                           │
│        Conditions:        │
│      ps_suppkey = #0      ├────────────────────────────────────────────────────────────────────────┐
│                           │                                                                        │
│                           │                                                                        │
│                           │                                                                        │
│       1,185,556 rows      │                                                                        │
│           0.02s           │                                                                        │
└─────────────┬─────────────┘                                                                        │
┌─────────────┴─────────────┐                                                          ┌─────────────┴─────────────┐
│         HASH_JOIN         │                                                          │         TABLE_SCAN        │
│    ────────────────────   │                                                          │    ────────────────────   │
│      Join Type: INNER     │                                                          │           Table:          │
│                           │                                                          │   "tpch-main-sf10".main   │
│        Conditions:        │                                                          │         .supplier         │
│   ps_partkey = p_partkey  │                                                          │                           │
│                           │                                                          │   Type: Sequential Scan   │
│                           │                                                          │                           │
│                           │                                                          │        Projections:       │
│                           ├──────────────┐                                           │         s_suppkey         │
│           0.13s           │              │                                           │                           │
│                           │              │                                           │          Filters:         │
│                           │              │                                           │  (s_comment ~~ '%Customer │
│                           │              │                                           │       %Complaints%')      │
│                           │              │                                           │                           │
│                           │              │                                           │                           │
│                           │              │                                           │                           │
│       1,185,556 rows      │              │                                           │          56 rows          │
│          (0.13s)          │              │                                           │           0.01s           │
└─────────────┬─────────────┘              │                                           └───────────────────────────┘
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│           Table:          ││             #0            │
│   "tpch-main-sf10".main   ││             #1            │
│         .partsupp         ││             #2            │
│                           ││             #3            │
│   Type: Sequential Scan   ││                           │
│                           ││                           │
│        Projections:       ││                           │
│         ps_partkey        ││                           │
│         ps_suppkey        ││           0.00s           │
│                           ││                           │
│      Dynamic Filters:     ││                           │
│  optional: ps_partkey>=2  ││                           │
│  AND optional: ps_partkey<││                           │
│   =1999995 AND optional:  ││                           │
│      ps_partkey IN BF     ││                           │
│        (p_partkey)        ││                           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│       1,185,556 rows      ││        296,389 rows       │
│           0.15s           ││          (0.00s)          │
└───────────────────────────┘└─────────────┬─────────────┘
                             ┌─────────────┴─────────────┐
                             │           FILTER          │
                             │    ────────────────────   │
                             │          IN (...)         │
                             │                           │
                             │                           │
                             │                           │
                             │        296,389 rows       │
                             │           0.01s           │
                             └─────────────┬─────────────┘
                             ┌─────────────┴─────────────┐
                             │         HASH_JOIN         │
    
... (truncated)
```
