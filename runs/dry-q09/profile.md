# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 1058.1 ms, total 1058 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q09 | 1058.1 | 100.0% |

## Plans with operator timings (slowest templates)

### q09.m0

```sql
SELECT nation, o_year, sum(amount) AS sum_profit FROM ( SELECT n_name AS nation, extract(year FROM o_orderdate) AS o_year, l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity AS amount FROM part, supplier, lineitem, partsupp, orders, nation WHERE s_suppkey = l_suppkey AND ps_suppkey = l_suppkey AND ps_partkey = l_partkey AND p_partkey = l_partkey AND o_orderkey = l_orderkey AND s_nationkey = n_nationkey AND p_name LIKE '%ghost%') AS profit GROUP BY nation, o_year ORDER BY nation, o_year DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││               Total Time: 1.39s              ││
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
│           0.28s           │
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
│           0.01s           │
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
│           0.08s           │
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
│           0.14s           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #0            │
│             #1            │
│             #2            │
│             #3            │
│__internal_decompress_strin│
│           g(#5)           │
│             #4            │
│                           │
│                           │
│                           │
│       3,269,453 rows      │
│           0.07s           │
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
│       3,269,453 rows      │                                                                        │
│           2.39s           │                                                                        │
└─────────────┬─────────────┘                                                                        │
┌─────────────┴─────────────┐                                                          ┌─────────────┴─────────────┐
│         PROJECTION        │                                                          │         PROJECTION        │
│    ────────────────────   │                                                          │    ────────────────────   │
│             #4            │                                                          │             #0            │
│             #0            │                                                          │             #1            │
│             #1            │                                                          │             #2            │
│             #2            │                                                          │__internal_compress_string_│
│             #3            │                                                          │        uhugeint(#3)       │
│             #5            │                                                          │                           │
│                           │                                                          │                           │
│                           │                                                          │                           │
│                           │                                                          │                           │
│       3,269,453 rows      │                                                          │           0.12s           │
│           0.02s           │                                                          │          (0.12s)          │
└─────────────┬─────────────┘                                                          └─────────────┬─────────────┘
┌─────────────┴─────────────┐                                                          ┌─────────────┴─────────────┐
│         HASH_JOIN         │                                                          │         HASH_JOIN         │
│    ────────────────────   │                                                          │    ────────────────────   │
│      Join Type: INNER     │                                                          │      Join Type: INNER     │
│                           │                                                          │                           │
│        Conditions:        │                                                          │        Conditions:        │
│  l_orderkey = o_orderkey  ├───────────────────────────────────────────┐              │   ps_suppkey = s_suppkey  ├──────────────┐
│                           │                                           │              │                           │              │
│                           │                                           │              │                           │              │
│                           │                                           │              │                           │              │
│       3,269,453 rows      │                                           │              │       8,000,000 rows      │              │
│           2.59s           │                                           │              │           0.03s           │              │
└─────────────┬─────────────┘                                           │              └─────────────┬─────────────┘              │
┌─────────────┴─────────────┐                             ┌─────────────┴─────────────┐┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         PROJECTION        │                             │         PROJECTION        ││         TABLE_SCAN        ││         HASH_JOIN         │
│    ────────────────────   │                             │    ────────────────────   ││    ────────────────────   ││    ────────────────────   │
│             #0            │                             │__internal_compress_integra││           Table:          ││      Join Type: INNER     │
│__internal_compress_integra│                             │     l_uinteger(#0, 1)     ││   "tpch-main-sf10".main   ││                           │
│     l_uinteger(#1, 1)     │                             │             #1            ││         .partsupp         ││        Conditions:        │
│             #2            │                             │                           ││                           ││ s_nationkey = n_nationkey │
│             #3            │                             │                           ││   Type: Sequential Scan   ││                           │
│             #4            │                             │                           ││                           ││                           │
│             #5            │                             │                           ││        Projections:       ││                           │
│                           │              
... (truncated)
```
