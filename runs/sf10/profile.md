# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 242.3 ms, total 4140 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q13 | 773.4 | 18.7% |
| q18 | 657.4 | 15.9% |
| q09 | 589.9 | 14.2% |
| q05 | 266.8 | 6.4% |
| q03 | 252.2 | 6.1% |
| q08 | 224.5 | 5.4% |
| q04 | 219.5 | 5.3% |
| q17 | 217.7 | 5.3% |
| q16 | 196.5 | 4.7% |
| q07 | 192.8 | 4.7% |
| q19 | 184.2 | 4.4% |
| q14 | 158.0 | 3.8% |
| q22 | 127.7 | 3.1% |
| q02 | 78.9 | 1.9% |

## Plans with operator timings (slowest templates)

### q13.m0

```sql
SELECT c_count, count(*) AS custdist FROM ( SELECT c_custkey, count(o_orderkey) FROM customer LEFT OUTER JOIN orders ON c_custkey = o_custkey AND o_comment NOT LIKE '%unusual%packages%' GROUP BY c_custkey) AS c_orders (c_custkey, c_count) GROUP BY c_count ORDER BY custdist DESC, c_count DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││               Total Time: 1.04s              ││
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
│           2.69s           │
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
│           2.06s           │              │
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
│        %packages%')       ││           0.06s           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│      14,833,270 rows      ││       1,500,000 rows      │
│           2.79s           ││          (0.06s)          │
└───────────────────────────┘└───────────────────────────┘
```

### q18.m0

```sql
SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS sum_qty FROM customer, orders, lineitem WHERE o_orderkey IN (SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 312) AND c_custkey = o_custkey AND o_orderkey = l_orderkey GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice ORDER BY o_totalprice DESC, o_orderdate, o_orderkey LIMIT 100
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
│           0.29s           │              │
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
│           0.17s           ││          (0.00s)          │
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
                             │           0.22s           │                                           │
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
││              Total Time: 0.755s              ││
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
│           0.21s           │
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
│           0.12s           │
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
│           0.03s           │                                                                                                     │
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
│           1.51s           ├──────────────┐                                                                        │        s_nationkey        ││           n_name          │
│                           │              │                                                                        │                           ││                           │
│                           │              │                                                                        │      Dynamic Filters:     ││                           │
│                           │              │                                                                        │  optional: s_nationkey>=0 ││                           │
│                           │              │                                                                  
... (truncated)
```

### q05.m0

```sql
SELECT n_name, sum(l_extendedprice * (1 - l_discount)) AS revenue FROM customer, orders, lineitem, supplier, nation, region WHERE c_custkey = o_custkey AND l_orderkey = o_orderkey AND l_suppkey = s_suppkey AND c_nationkey = s_nationkey AND s_nationkey = n_nationkey AND n_regionkey = r_regionkey AND r_name = 'EUROPE' AND o_orderdate >= DATE '1995-01-01' AND o_orderdate < DATE '1995-01-01' + INTERVAL '1' YEAR GROUP BY n_name ORDER BY revenue DESC, n_name
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.343s              ││
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
│                           │
│                           │
│                           │
│           5 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          ORDER_BY         │
│    ────────────────────   │
│ sum(("tpch-main-sf10".main│
│ .lineitem.l_extendedprice │
│  * (1 - "tpch-main-sf10"  │
│ .main.lineitem.l_discount)│
│          )) DESC          │
│   "tpch-main-sf10".main   │
│     .nation.n_name ASC    │
│                           │
│                           │
│                           │
│           5 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_string_│
│        uhugeint(#0)       │
│             #1            │
│                           │
│                           │
│                           │
│           5 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_strin│
│           g(#0)           │
│             #1            │
│                           │
│                           │
│                           │
│           5 rows          │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│         Groups: #0        │
│    Aggregates: sum(#1)    │
│                           │
│                           │
│                           │
│           5 rows          │
│           0.01s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│           n_name          │
│ (l_extendedprice * (1.00 -│
│        l_discount))       │
│                           │
│                           │
│                           │
│        72,637 rows        │
│           0.00s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_string_│
│        uhugeint(#2)       │
│             #0            │
│             #1            │
│__internal_compress_integra│
│     l_uinteger(#3, 1)     │
│__internal_compress_integra│
│     l_utinyint(#4, 0)     │
│                           │
│                           │
│                           │
│        72,637 rows        │
│           0.01s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: INNER     │
│                           │
│        Conditions:        │
│ c_nationkey = s_nationkey │
│   l_suppkey = s_suppkey   ├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           │                                                                                                                                  │
│                           │                                                                                                                                  │
│                           │                                                                                                                                  │
│        72,637 rows        │                                                                                                                                  │
│           0.14s           │                                                                                                                                  │
└─────────────┬─────────────┘                                                                                                                                  │
┌─────────────┴─────────────┐                                                                                                                    ┌─────────────┴─────────────┐
│         HASH_JOIN         │                                                                                                                    │         TABLE_SCAN        │
│    ────────────────────   │                                                                                                                    │    ────────────────────   │
│      Join Type: INNER     │                                                                                                                    │           Table:          │
│                           │                                                                                                                    │   "tpch-main-sf10".main   │
│        Conditions:        │                                                                                                                    │         .supplier         │
│  l_orderkey = o_orderkey  │                                                                                                                    │                           │
│                           │                                                                                                                    │   Type: Sequential Scan   │
│                           │                                                                                                                    │                           │
│                           ├──────────────┐                                                                                                     │        Projections:       │
│                           │              │                                                                                                     │         s_suppkey         │
│           0.38s           │              │                                                                                                     │        s_nationkey        │
│                           │              │                                                                                                     │                           │
│                           │              │                                                                                                     │                           │
│                           │              │                                                                                                     │                           │
│       1,822,365 rows      │              │                                                                                                     │        100,000 rows       │
│          (0.38s)          │              │                                                                                                     │           0.00s           │
└─────────────┬─────────────┘              │                                                                                                     └───────────────────────────┘
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         HASH_JOIN         │
│    ────────────────────   ││    ────────────────────   │
│           Table:          ││      Join Type: INNER     │
│   "tpch-main-sf10".main   ││                           │
│         .lineitem         ││        Conditions:        │
│                           ││   o_custkey = c_custkey   │
│   Type: Sequential Scan   ││                           │
│                           ││                           │
│        Projections:       ││                           │
│         l_orderkey        ││                           │
│         l_suppkey         ││           0.18s           │
│      l_extendedprice      ││                           │
│         l_discount        ││                           ├──────────────┐
│                           ││                           │              │
│      Dynamic Filters:     ││                           │              │
│  optional: l_orderkey>=65 ││                           │              │
│  AND optional: l_orderkey<││                           │              │
│  =59999905 AND optional:  ││                           │              │
│      l_orderkey IN BF     ││                           │              │
│        (o_orderkey)       ││                           │              │
│                           ││                           │              │
│                           ││                           │              │
│                           ││                           │              │
│       2,034,865 rows      ││        455,641 rows       │              │
│           1.04s           ││          (0.18s)          │              │
└───────────────────────────┘└─────────────┬─────────────┘              │
                             ┌─────────────┴─────────────┐┌─────────────┴─────────────┐
                             │         TABLE_SCAN        ││         HASH_JOIN         │
                             │    ────────────────────   ││    ────────────────────   │
                             │           Table:          ││      Join Type: INNER     │
                             │   "tpch-main
... (truncated)
```
