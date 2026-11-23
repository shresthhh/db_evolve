# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 292.7 ms, total 3321 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q21 | 775.4 | 23.3% |
| q13 | 704.2 | 21.2% |
| q18 | 635.2 | 19.1% |
| q09 | 561.3 | 16.9% |
| q01 | 290.6 | 8.7% |
| q16 | 168.3 | 5.1% |
| q19 | 147.9 | 4.5% |
| q02 | 38.2 | 1.2% |

## Plans with operator timings (slowest templates)

### q21.m0

```sql
SELECT s_name, count(*) AS numwait FROM supplier, lineitem l1, orders, nation WHERE s_suppkey = l1.l_suppkey AND o_orderkey = l1.l_orderkey AND o_orderstatus = 'F' AND l1.l_receiptdate > l1.l_commitdate AND EXISTS (SELECT * FROM lineitem l2 WHERE l2.l_orderkey = l1.l_orderkey AND l2.l_suppkey <> l1.l_suppkey) AND NOT EXISTS (SELECT * FROM lineitem l3 WHERE l3.l_orderkey = l1.l_orderkey AND l3.l_suppkey <> l1.l_suppkey AND l3.l_receiptdate > l3.l_commitdate) AND s_nationkey = n_nationkey AND n_name = 'JAPAN' GROUP BY s_name ORDER BY numwait DESC, s_name LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││               Total Time: 1.06s              ││
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
│                 │                                                                  │                                                        │         │      0.28s      │         │                            │                 │
│                 │                                                                  │                                                        │         │                 │         │                            │                 │
│      0 rows     │                                                                  │                                                        │         │   40,074 rows   │         │                            │   708,431 rows  │
│      0.34s      │                                                                  │                                                        │         │     (0.28s)     │         │                            │     (0.03s)     │
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
││              Total Time: 0.806s              ││
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
│       HASH_GROUP_BY       │
│    ────────────────────   │
│         Groups: #0        │
│   Aggregates: count(#1)   │
│                           │
│                           │
│                           │
│       1,500,000 rows      │
│           2.23s           │
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
│           0.02s           │
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
│           0.03s           │
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
│           1.29s           │              │
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
│           2.47s           ││          (0.01s)          │
└───────────────────────────┘└───────────────────────────┘
```

### q18.m0

```sql
SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS sum_qty FROM customer, orders, lineitem WHERE o_orderkey IN (SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 312) AND c_custkey = o_custkey AND o_orderkey = l_orderkey GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice ORDER BY o_totalprice DESC, o_orderdate, o_orderkey LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.731s              ││
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
│ .orders.o_totalprice DESC │
│   "tpch-main-sf10".main   │
│  .orders.o_orderdate ASC  │
│   "tpch-main-sf10".main   │
│   .orders.o_orderkey ASC  │
│                           │
│                           │
│                           │
│          100 rows         │
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
│          111 rows         │
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
│          111 rows         │
│           0.01s           │
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
│          777 rows         │
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
│          777 rows         │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│__internal_decompress_integ│
│     ral_bigint(#1, 1)     │
│             #2            │
│             #3            │
│__internal_decompress_integ│
│     ral_bigint(#4, 1)     │
│             #5            │
│                           │
│                           │
│                           │
│          777 rows         │
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
│          777 rows         │              │
│           0.26s           │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         PROJECTION        ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│__internal_compress_integra││__internal_compress_integra│
│     l_uinteger(#0, 1)     ││     l_uinteger(#0, 1)     │
│             #1            ││             #1            │
│                           ││             #2            │
│                           ││__internal_compress_integra│
│                           ││     l_uinteger(#3, 1)     │
│                           ││             #4            │
│           0.03s           ││                           │
│                           ││                           │
│                           ││                           │
│      59,986,052 rows      ││          111 rows         │
│          (0.03s)          ││           0.00s           │
└─────────────┬─────────────┘└─────────────┬─────────────┘
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│           Table:          ││             #0            │
│   "tpch-main-sf10".main   ││             #1            │
│         .lineitem         ││             #2            │
│                           ││__internal_decompress_integ│
│   Type: Sequential Scan   ││     ral_bigint(#3, 1)     │
│                           ││             #4            │
│        Projections:       ││                           │
│         l_orderkey        ││                           │
│         l_quantity        ││                           │
│                           ││                           │
│                           ││           0.00s           │
│                           ││                           │
│      59,986,052 rows      ││          111 rows         │
│           0.18s           ││          (0.00s)          │
└───────────────────────────┘└─────────────┬─────────────┘
                             ┌─────────────┴─────────────┐
                             │         HASH_JOIN         │
                             │    ────────────────────   │
                             │      Join Type: INNER     │
                             │                           │
                             │        Conditions:        │
                             │   o_custkey = c_custkey   ├───────────────────────────────────────────┐
                             │                           │                                           │
                             │                           │                                           │
                             │                           │                                           │
                             │          111 rows         │                                           │
                             │           0.26s           │                                           │
                             └─────────────┬─────────────┘                                           │
                             ┌─────────────┴─────────────┐                             ┌─────────────┴─────────────┐
                             │         PROJECTION        │                             │         PROJECTION        │
                             │    ────────────────────   │                             │    ────────────────────   │
                             │             #0            │                             │__internal_compress_integra│
                             │__internal_compress_integra│                             │     l_uinteger(#0, 1)     │
                             │     l_uinteger(#1, 1)     │                             │             #1            │
                             │             #2            │                             │                           │
                             │             #3            │                             │                           │
                             │                           │                             │                           │
                             │                           │                             │                           │
                             │                           │                             │           0.00s           │
                             │          111 rows         │                             │       1,499,999 rows      │
                             │           0.00s           │                             │          (0.00s)          │
                             └─────────────┬─────────────┘                             └─────────────┬─────────────┘
                             ┌─────────────┴─────────────┐                             ┌─────────────┴─────────────┐
                             │         PROJECTION        │                             │         TABLE_SCAN        │
                             │    ────────────────────   │                             │    ────────────────────   │
                             │__internal_decompress_integ│                             │           Table:          │
                             │     ral_bigint(#0, 1)     │                             │   "tpch-main-sf10".main   │
                             │             #1            │                             │         .customer         │
                             │             #2            │                             │                           │
                             │             #3            │                             │   Type: Sequential Scan   │
                             │                           │                             │                           │
                             │                           │                             │        Projections:       │
                             │ 
... (truncated)
```

### q09.m0

```sql
SELECT nation, o_year, sum(amount) AS sum_profit FROM ( SELECT n_name AS nation, extract(year FROM o_orderdate) AS o_year, l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity AS amount FROM part, supplier, lineitem, partsupp, orders, nation WHERE s_suppkey = l_suppkey AND ps_suppkey = l_suppkey AND ps_partkey = l_partkey AND p_partkey = l_partkey AND o_orderkey = l_orderkey AND s_nationkey = n_nationkey AND p_name LIKE '%ghost%') AS profit GROUP BY nation, o_year ORDER BY nation, o_year DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.700s              ││
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
│           0.20s           │
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
│       3,269,453 rows      │
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
│       3,269,453 rows      │
│           0.11s           │
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
│       3,269,453 rows      │
│           0.05s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: INNER     │
│                           │
│        Conditions:        │
│   l_suppkey = s_suppkey   ├─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           │                                                                                                     │
│                           │                                                                                                     │
│                           │                                                                                                     │
│       3,269,453 rows      │                                                                                                     │
│           0.02s           │                                                                                                     │
└─────────────┬─────────────┘                                                                                                     │
┌─────────────┴─────────────┐                                                                                       ┌─────────────┴─────────────┐
│         PROJECTION        │                                                                                       │         HASH_JOIN         │
│    ────────────────────   │                                                                                       │    ────────────────────   │
│             #0            │                                                                                       │      Join Type: INNER     │
│__internal_decompress_integ│                                                                                       │                           │
│     ral_bigint(#4, 1)     │                                                                                       │        Conditions:        │
│             #5            │                                                                                       │ s_nationkey = n_nationkey │
│             #1            │                                                                                       │                           │
│             #2            │                                                                                       │                           ├──────────────┐
│             #3            │                                                                                       │                           │              │
│                           │                                                                                       │                           │              │
│                           │                                                                                       │           0.00s           │              │
│                           │                                                                                       │                           │              │
│       3,269,453 rows      │                                                                                       │        100,000 rows       │              │
│           0.02s           │                                                                                       │          (0.00s)          │              │
└─────────────┬─────────────┘                                                                                       └─────────────┬─────────────┘              │
┌─────────────┴─────────────┐                                                                                       ┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         HASH_JOIN         │                                                                                       │         TABLE_SCAN        ││         TABLE_SCAN        │
│    ────────────────────   │                                                                                       │    ────────────────────   ││    ────────────────────   │
│      Join Type: INNER     │                                                                                       │           Table:          ││           Table:          │
│                           │                                                                                       │   "tpch-main-sf10".main   ││   "tpch-main-sf10".main   │
│        Conditions:        │                                                                                       │         .supplier         ││          .nation          │
│  o_orderkey = l_orderkey  │                                                                                       │                           ││                           │
│                           │                                                                                       │   Type: Sequential Scan   ││   Type: Sequential Scan   │
│                           │                                                                                       │                           ││                           │
│                           │                                                                                       │        Projections:       ││        Projections:       │
│                           │                                                                                       │         s_suppkey         ││        n_nationkey        │
│           1.17s           ├──────────────┐                                                                        │        s_nationkey        ││           n_name          │
│                           │              │                                                                        │                           ││                           │
│                           │              │                                                                        │      Dynamic Filters:     ││                           │
│                           │              │                                                                        │  optional: s_nationkey>=0 ││                           │
│                           │              │                                                                  
... (truncated)
```
