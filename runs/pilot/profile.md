# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 43.5 ms, total 703 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q09 | 121.3 | 17.2% |
| q13 | 105.2 | 15.0% |
| q18 | 87.3 | 12.4% |
| q16 | 49.3 | 7.0% |
| q19 | 47.2 | 6.7% |
| q22 | 42.5 | 6.1% |
| q03 | 39.3 | 5.6% |
| q07 | 36.7 | 5.2% |
| q05 | 35.8 | 5.1% |
| q04 | 34.8 | 4.9% |
| q08 | 30.5 | 4.3% |
| q14 | 28.0 | 4.0% |
| q02 | 23.5 | 3.3% |
| q17 | 21.8 | 3.1% |

## Plans with operator timings (slowest templates)

### q09.m0

```sql
SELECT nation, o_year, sum(amount) AS sum_profit FROM ( SELECT n_name AS nation, extract(year FROM o_orderdate) AS o_year, l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity AS amount FROM part, supplier, lineitem, partsupp, orders, nation WHERE s_suppkey = l_suppkey AND ps_suppkey = l_suppkey AND ps_partkey = l_partkey AND p_partkey = l_partkey AND o_orderkey = l_orderkey AND s_nationkey = n_nationkey AND p_name LIKE '%ghost%') AS profit GROUP BY nation, o_year ORDER BY nation, o_year DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.181s              ││
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
│__internal_decompress_integ│
│    ral_bigint(#1, 1992)   │
│             #2            │
│                           │
│                           │
│                           │
│          175 rows         │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          ORDER_BY         │
│    ────────────────────   │
│     profit.nation ASC     │
│     profit.o_year DESC    │
│                           │
│                           │
│                           │
│          175 rows         │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_string_│
│        uhugeint(#0)       │
│__internal_compress_integra│
│    l_utinyint(#1, 1992)   │
│             #2            │
│                           │
│                           │
│                           │
│          175 rows         │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_strin│
│           g(#0)           │
│__internal_decompress_integ│
│    ral_bigint(#1, 1992)   │
│             #2            │
│                           │
│                           │
│                           │
│          175 rows         │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│          Groups:          │
│             #0            │
│             #1            │
│                           │
│    Aggregates: sum(#2)    │
│                           │
│                           │
│                           │
│          175 rows         │
│           0.04s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│           nation          │
│           o_year          │
│           amount          │
│                           │
│                           │
│                           │
│        324,507 rows       │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_string_│
│        uhugeint(#0)       │
│__internal_compress_integra│
│    l_utinyint(#1, 1992)   │
│             #2            │
│                           │
│                           │
│                           │
│        324,507 rows       │
│           0.01s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│           nation          │
│           o_year          │
│           amount          │
│                           │
│                           │
│                           │
│        324,507 rows       │
│           0.01s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: INNER     │
│                           │
│        Conditions:        │
│   p_partkey = ps_partkey  │
│   l_suppkey = ps_suppkey  ├────────────────────────────────────────────────────────────────────────┐
│                           │                                                                        │
│                           │                                                                        │
│                           │                                                                        │
│        324,507 rows       │                                                                        │
│           0.24s           │                                                                        │
└─────────────┬─────────────┘                                                                        │
┌─────────────┴─────────────┐                                                          ┌─────────────┴─────────────┐
│         PROJECTION        │                                                          │         HASH_JOIN         │
│    ────────────────────   │                                                          │    ────────────────────   │
│             #4            │                                                          │      Join Type: INNER     │
│             #0            │                                                          │                           │
│             #1            │                                                          │        Conditions:        │
│             #2            │                                                          │   ps_suppkey = s_suppkey  │
│             #3            │                                                          │                           ├──────────────┐
│             #5            │                                                          │                           │              │
│                           │                                                          │                           │              │
│                           │                                                          │                           │              │
│                           │                                                          │           0.00s           │              │
│        324,507 rows       │                                                          │        800,000 rows       │              │
│           0.00s           │                                                          │          (0.00s)          │              │
└─────────────┬─────────────┘                                                          └─────────────┬─────────────┘              │
┌─────────────┴─────────────┐                                                          ┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         HASH_JOIN         │                                                          │         TABLE_SCAN        ││         HASH_JOIN         │
│    ────────────────────   │                                                          │    ────────────────────   ││    ────────────────────   │
│      Join Type: INNER     │                                                          │           Table:          ││      Join Type: INNER     │
│                           │                                                          │ "tpch-main".main.partsupp ││                           │
│        Conditions:        │                                                          │                           ││        Conditions:        │
│  l_orderkey = o_orderkey  │                                                          │   Type: Sequential Scan   ││ s_nationkey = n_nationkey │
│                           │                                                          │                           ││                           │
│                           │                                                          │        Projections:       ││                           │
│                           │                                                          │         ps_suppkey        ││                           │
│                           │                                                          │         ps_partkey        ││                           │
│           0.28s           ├───────────────────────────────────────────┐              │       ps_supplycost       ││           0.00s           ├──────────────┐
│                           │                                           │              │                           ││                           │              │
│                           │                                           │              │      Dynamic Filters:     ││                           │              │
│                           │                                           │              │  optional: ps_suppkey>=1  ││                           │              │
│                           │                                           │              │  AND optional: ps_suppkey<││                           │              │
│                           │                                           │              │           =10000          ││                           │              │
│                           │                                           │              │                           ││                           │              │
│                           │                                           │              │                           ││                           │              │
│                           │                                           │              │                           ││                           │              │
│        324,507 rows       │                                           │              │        800,000 rows       ││        10,000 rows        │              │
│          (0.28s)          │                                           │              │           0.03s           ││          (0.00s)          │              │
└─────────────┬─────────────┘                                           │              └────────────────────────
... (truncated)
```

### q13.m0

```sql
SELECT c_count, count(*) AS custdist FROM ( SELECT c_custkey, count(o_orderkey) FROM customer LEFT OUTER JOIN orders ON c_custkey = o_custkey AND o_comment NOT LIKE '%unusual%packages%' GROUP BY c_custkey) AS c_orders (c_custkey, c_count) GROUP BY c_count ORDER BY custdist DESC, c_count DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.104s              ││
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
│          42 rows          │
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
│          42 rows          │
│           0.01s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          c_count          │
│                           │
│                           │
│                           │
│        150,000 rows       │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│     count(o_orderkey)     │
│                           │
│                           │
│                           │
│        150,000 rows       │
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
│        150,000 rows       │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│         Groups: #0        │
│   Aggregates: count(#1)   │
│                           │
│                           │
│                           │
│        150,000 rows       │
│           0.21s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│         c_custkey         │
│         o_orderkey        │
│                           │
│                           │
│                           │
│       1,533,127 rows      │
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
│       1,533,127 rows      │
│           0.00s           │
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
│       1,533,127 rows      │              │
│           0.11s           │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         TABLE_SCAN        │
│    ────────────────────   ││    ────────────────────   │
│           Table:          ││           Table:          │
│  "tpch-main".main.orders  ││ "tpch-main".main.customer │
│                           ││                           │
│   Type: Sequential Scan   ││   Type: Sequential Scan   │
│                           ││                           │
│        Projections:       ││        Projections:       │
│         o_custkey         ││         c_custkey         │
│         o_orderkey        ││                           │
│                           ││                           │
│          Filters:         ││                           │
│  (o_comment !~~ '%unusual ││                           │
│        %packages%')       ││           0.00s           │
│                           ││                           │
│      Dynamic Filters:     ││                           │
│ optional: o_custkey>=1 AND││                           │
│    optional: o_custkey<   ││                           │
│          =150000          ││                           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│       1,483,123 rows      ││        150,000 rows       │
│           0.23s           ││          (0.00s)          │
└───────────────────────────┘└───────────────────────────┘
```

### q18.m0

```sql
SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS sum_qty FROM customer, orders, lineitem WHERE o_orderkey IN (SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 312) AND c_custkey = o_custkey AND o_orderkey = l_orderkey GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice ORDER BY o_totalprice DESC, o_orderdate, o_orderkey LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.0855s             ││
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
│  "tpch-main".main.orders  │
│     .o_totalprice DESC    │
│  "tpch-main".main.orders  │
│      .o_orderdate ASC     │
│  "tpch-main".main.orders  │
│      .o_orderkey ASC      │
│                           │
│                           │
│                           │
│          10 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│__internal_decompress_integ│
│     ral_bigint(#1, 1)     │
│__internal_decompress_integ│
│     ral_bigint(#2, 1)     │
│             #3            │
│             #4            │
│             #5            │
│                           │
│                           │
│                           │
│          10 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│          Groups:          │
│             #0            │
│             #1            │
│             #2            │
│             #3            │
│             #4            │
│                           │
│    Aggregates: sum(#5)    │
│                           │
│                           │
│                           │
│          10 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│           c_name          │
│         c_custkey         │
│         o_orderkey        │
│        o_orderdate        │
│        o_totalprice       │
│         l_quantity        │
│                           │
│                           │
│                           │
│          70 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│__internal_compress_integra│
│     l_uinteger(#1, 1)     │
│             #2            │
│             #3            │
│__internal_compress_integra│
│     l_uinteger(#4, 1)     │
│             #5            │
│                           │
│                           │
│                           │
│          70 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: INNER     │
│                           │
│        Conditions:        │
│  l_orderkey = o_orderkey  ├──────────────┐
│                           │              │
│                           │              │
│                           │              │
│          70 rows          │              │
│           0.00s           │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         HASH_JOIN         │
│    ────────────────────   ││    ────────────────────   │
│           Table:          ││      Join Type: INNER     │
│ "tpch-main".main.lineitem ││                           │
│                           ││        Conditions:        │
│   Type: Sequential Scan   ││   o_custkey = c_custkey   │
│                           ││                           │
│        Projections:       ││                           │
│         l_orderkey        ││                           │
│         l_quantity        ││                           │
│                           ││           0.01s           │
│      Dynamic Filters:     ││                           │
│  optional: l_orderkey IN  ││                           │
│ (1263015, 1544643, 2199712││                           ├───────────────────────────────────────────┐
│    , 2869152, 2942469,    ││                           │                                           │
│  3043270, 3767271, 4702759││                           │                                           │
│  , 4722021, 4806726) AND  ││                           │                                           │
│    optional: l_orderkey>  ││                           │                                           │
│   =1263015 AND optional:  ││                           │                                           │
│   l_orderkey<=4806726 AND ││                           │                                           │
│   optional: l_orderkey IN ││                           │                                           │
│       BF(o_orderkey)      ││                           │                                           │
│                           ││                           │                                           │
│                           ││                           │                                           │
│                           ││                           │                                           │
│          248 rows         ││          10 rows          │                                           │
│           0.01s           ││          (0.01s)          │                                           │
└───────────────────────────┘└─────────────┬─────────────┘                                           │
                             ┌─────────────┴─────────────┐                             ┌─────────────┴─────────────┐
                             │         HASH_JOIN         │                             │         TABLE_SCAN        │
                             │    ────────────────────   │                             │    ────────────────────   │
                             │      Join Type: SEMI      │                             │           Table:          │
                             │                           │                             │ "tpch-main".main.customer │
                             │        Conditions:        │                             │                           │
                             │      o_orderkey = #0      │                             │   Type: Sequential Scan   │
                             │                           │                             │                           │
                             │                           │                             │        Projections:       │
                             │                           │                             │         c_custkey         │
                             │                           ├──────────────┐              │           c_name          │
                             │           0.00s           │              │              │                           │
                             │                           │              │              │          Filters:         │
                             │                           │              │              │     c_custkey<=149999     │
                             │                           │              │              │                           │
                             │                           │              │              │                           │
                             │                           │              │              │                           │
                             │          10 rows          │              │              │        149,999 rows       │
                             │          (0.00s)          │              │              │           0.00s           │
                             └─────────────┬─────────────┘              │              └───────────────────────────┘
                             ┌─────────────┴─────────────┐┌─────────────┴─────────────┐
                             │         TABLE_SCAN        ││         PROJECTION        │
                             │    ────────────────────   ││    ────────────────────   │
                             │           Table:          ││             #0            │
                             │  "tpch-main".main.orders  ││                           │
                             │                           ││                           │
                             │   Type: Sequential Scan   ││                           │
                             │                           ││                           │
                             │        Projections:       ││           0.00s           │
                             │         o_orderkey        ││                           │
                             │         o_custkey         ││                           │
                             │        o_orderdate        ││                           │
                             │        o_totalprice       ││                           │
                             │                           ││                           │
                             │      Dynamic Filters:     ││                           │
                             │  optional: o_orderkey IN  ││                           │
                             │ (1263015, 1544643, 2199712││                           │
                             │    , 2869152, 2942469,    ││                           │
                             │  3043270, 3767271, 4702759││                           │
                             │  , 4722021, 4806
... (truncated)
```

### q16.m0

```sql
SELECT p_brand, p_type, p_size, count(DISTINCT ps_suppkey) AS supplier_cnt FROM partsupp, part WHERE p_partkey = ps_partkey AND p_brand <> 'Brand#51' AND p_type NOT LIKE 'MEDIUM PLATED%' AND p_size IN (29, 2, 23, 11, 13, 1, 46, 40) AND ps_suppkey NOT IN (SELECT s_suppkey FROM supplier WHERE s_comment LIKE '%Customer%Complaints%') GROUP BY p_brand, p_type, p_size ORDER BY supplier_cnt DESC, p_brand, p_type, p_size
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.0358s             ││
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
│        18,290 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          ORDER_BY         │
│    ────────────────────   │
│ count(DISTINCT "tpch-main"│
│ .main.partsupp.ps_suppkey)│
│            DESC           │
│   "tpch-main".main.part   │
│        .p_brand ASC       │
│   "tpch-main".main.part   │
│        .p_type ASC        │
│   "tpch-main".main.part   │
│        .p_size ASC        │
│                           │
│                           │
│                           │
│        18,290 rows        │
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
│        18,290 rows        │
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
│        18,290 rows        │
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
│        18,290 rows        │
│           0.03s           │
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
│        119,003 rows       │
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
│        119,003 rows       │
│           0.00s           │
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
│        119,003 rows       │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           FILTER          │
│    ────────────────────   │
│       (NOT SUBQUERY)      │
│                           │
│                           │
│                           │
│        119,003 rows       │
│           0.00s           │
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
│        119,044 rows       │                                                                        │
│           0.00s           │                                                                        │
└─────────────┬─────────────┘                                                                        │
┌─────────────┴─────────────┐                                                          ┌─────────────┴─────────────┐
│         HASH_JOIN         │                                                          │         TABLE_SCAN        │
│    ────────────────────   │                                                          │    ────────────────────   │
│      Join Type: INNER     │                                                          │           Table:          │
│                           │                                                          │ "tpch-main".main.supplier │
│        Conditions:        │                                                          │                           │
│   ps_partkey = p_partkey  │                                                          │   Type: Sequential Scan   │
│                           │                                                          │                           │
│                           │                                                          │        Projections:       │
│                           │                                                          │         s_suppkey         │
│                           ├──────────────┐                                           │                           │
│           0.01s           │              │                                           │          Filters:         │
│                           │              │                                           │  (s_comment ~~ '%Customer │
│                           │              │                                           │       %Complaints%')      │
│                           │              │                                           │                           │
│                           │              │                                           │                           │
│                           │              │                                           │                           │
│        119,044 rows       │              │                                           │           4 rows          │
│          (0.01s)          │              │                                           │           0.00s           │
└─────────────┬─────────────┘              │                                           └───────────────────────────┘
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│           Table:          ││             #0            │
│ "tpch-main".main.partsupp ││             #1            │
│                           ││             #2            │
│   Type: Sequential Scan   ││             #3            │
│                           ││                           │
│        Projections:       ││                           │
│         ps_partkey        ││                           │
│         ps_suppkey        ││                           │
│                           ││           0.00s           │
│      Dynamic Filters:     ││                           │
│  optional: ps_partkey>=2  ││                           │
│  AND optional: ps_partkey<││                           │
│          =199996          ││                           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│        799,996 rows       ││        29,761 rows        │
│           0.00s           ││          (0.00s)          │
└───────────────────────────┘└─────────────┬─────────────┘
                             ┌─────────────┴─────────────┐
                             │           FILTER          │
                             │    ────────────────────   │
                             │          IN (...)         │
                             │                           │
                             │                           │
                             │                           │
                             │        29,761 rows        │
                             │           0.00s           │
                             └─────────────┬─────────────┘
                             ┌─────────────┴─────────────┐
                             │         HASH_JOIN         │
                             │    ────────────────────   │
                             │      Join Type: MARK      │
                             │                           │
                             │        Conditions:        │
                             │        p_size = #0        ├────
... (truncated)
```
