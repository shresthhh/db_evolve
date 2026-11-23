# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 223.4 ms, total 1632 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q18 | 649.4 | 39.8% |
| q09 | 512.9 | 31.4% |
| q01 | 283.9 | 17.4% |
| q19 | 144.7 | 8.9% |
| q02 | 40.7 | 2.5% |

## Plans with operator timings (slowest templates)

### q18.m0

```sql
SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS sum_qty FROM customer, orders, lineitem WHERE o_orderkey IN (SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 312) AND c_custkey = o_custkey AND o_orderkey = l_orderkey GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice ORDER BY o_totalprice DESC, o_orderdate, o_orderkey LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.791s              ││
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
│           0.22s           │              │
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
│           0.16s           ││          (0.00s)          │
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
                             │           0.28s           │                                           │
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
││              Total Time: 0.663s              ││
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
│           0.22s           │
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
│           0.13s           │
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
│           1.17s           ├──────────────┐                                                                        │        s_nationkey        ││           n_name          │
│                           │              │                                                                        │                           ││                           │
│                           │              │                                                                        │      Dynamic Filters:     ││                           │
│                           │              │                                                                        │  optional: s_nationkey>=0 ││                           │
│                           │              │                                                                  
... (truncated)
```

### q01.m0

```sql
SELECT l_returnflag, l_linestatus, sum(l_quantity) AS sum_qty, sum(l_extendedprice) AS sum_base_price, sum(l_extendedprice * (1 - l_discount)) AS sum_disc_price, sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS sum_charge, avg(l_quantity) AS avg_qty, avg(l_extendedprice) AS avg_price, avg(l_discount) AS avg_disc, count(*) AS count_order FROM lineitem WHERE l_shipdate <= DATE '1998-12-01' - INTERVAL '108' DAY GROUP BY l_returnflag, l_linestatus ORDER BY l_returnflag, l_linestatus
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.320s              ││
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
│           1.12s           │
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
│           0.90s           │
└───────────────────────────┘
```

### q19.m0

```sql
SELECT sum(l_extendedprice * (1 - l_discount)) AS revenue FROM lineitem, part WHERE (p_partkey = l_partkey AND p_brand = 'Brand#45' AND p_container IN ('SM CASE', 'SM BOX', 'SM PACK', 'SM PKG') AND l_quantity >= 9 AND l_quantity <= 9 + 10 AND p_size BETWEEN 1 AND 5 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON') OR (p_partkey = l_partkey AND p_brand = 'Brand#33' AND p_container IN ('MED BAG', 'MED BOX', 'MED PKG', 'MED PACK') AND l_quantity >= 20 AND l_quantity <= 20 + 10 AND p_size BETWEEN 1 AND 10 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON') OR (p_partkey = l_partkey AND p_brand = 'Brand#41' AND p_container IN ('LG CASE', 'LG BOX', 'LG PACK', 'LG PKG') AND l_quantity >= 23 AND l_quantity <= 23 + 10 AND p_size BETWEEN 1 AND 15 AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON')
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.227s              ││
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
│          (0.00s)          ││           0.13s           │
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
│           0.09s           ││         p_partkey         │
│                           ││          p_brand          │
│                           ││        p_container        │
│                           ││           p_size          │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│        11,797 rows        ││       2,000,000 rows      │
│          (0.09s)          ││           0.02s           │
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
│           1.32s           │
└───────────────────────────┘
```
