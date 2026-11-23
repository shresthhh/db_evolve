# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 286.4 ms, total 640 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q13 | 462.5 | 72.3% |
| q16 | 177.4 | 27.7% |

## Plans with operator timings (slowest templates)

### q13.m0

```sql
SELECT c_count, count(*) AS custdist FROM ( SELECT c_custkey, count(o_orderkey) FROM customer LEFT OUTER JOIN orders ON c_custkey = o_custkey AND o_comment NOT LIKE '%unusual%packages%' GROUP BY c_custkey) AS c_orders (c_custkey, c_count) GROUP BY c_count ORDER BY custdist DESC, c_count DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.710s              ││
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
│           0.07s           │
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
│           0.50s           │
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
│           0.18s           │
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
│           0.29s           │              │
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
│        %packages%')       ││           0.02s           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│      14,833,270 rows      ││       1,500,000 rows      │
│           2.67s           ││          (0.02s)          │
└───────────────────────────┘└───────────────────────────┘
```

### q16.m0

```sql
SELECT p_brand, p_type, p_size, count(DISTINCT ps_suppkey) AS supplier_cnt FROM partsupp, part WHERE p_partkey = ps_partkey AND p_brand <> 'Brand#51' AND p_type NOT LIKE 'MEDIUM PLATED%' AND p_size IN (29, 2, 23, 11, 13, 1, 46, 40) AND ps_suppkey NOT IN (SELECT s_suppkey FROM supplier WHERE s_comment LIKE '%Customer%Complaints%') GROUP BY p_brand, p_type, p_size ORDER BY supplier_cnt DESC, p_brand, p_type, p_size
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.183s              ││
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
│           0.17s           │              │                                           │                           │
│                           │              │                                           │          Filters:         │
│                           │              │                                           │  (s_comment ~~ '%Customer │
│                           │              │                                           │       %Complaints%')      │
│                           │              │                                           │                           │
│                           │              │                                           │                           │
│                           │              │                                           │                           │
│       1,185,556 rows      │              │                                           │          56 rows          │
│          (0.17s)          │              │                                           │           0.01s           │
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
│       1,236,280 rows      ││        296,389 rows       │
│           0.17s           ││          (0.00s)          │
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
