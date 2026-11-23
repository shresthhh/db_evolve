# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 444.3 ms, total 444 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q09 | 444.3 | 100.0% |

## Plans with operator timings (slowest templates)

### q09.m0

```sql
SELECT nation, o_year, sum(amount) AS sum_profit FROM ( SELECT n_name AS nation, extract(year FROM o_orderdate) AS o_year, l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity AS amount FROM part, supplier, lineitem, partsupp, orders, nation WHERE s_suppkey = l_suppkey AND ps_suppkey = l_suppkey AND ps_partkey = l_partkey AND p_partkey = l_partkey AND o_orderkey = l_orderkey AND s_nationkey = n_nationkey AND p_name LIKE '%ghost%') AS profit GROUP BY nation, o_year ORDER BY nation, o_year DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.783s              ││
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
│           0.18s           │
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
│           0.16s           │
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
│           1.31s           ├──────────────┐                                                                        │        s_nationkey        ││           n_name          │
│                           │              │                                                                        │                           ││                           │
│                           │              │                                                                        │      Dynamic Filters:     ││                           │
│                           │              │                                                                        │  optional: s_nationkey>=0 ││                           │
│                           │              │                                                                  
... (truncated)
```
