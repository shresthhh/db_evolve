# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 121.3 ms, total 1872 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q09 | 304.9 | 16.3% |
| q13 | 226.2 | 12.1% |
| q18 | 172.2 | 9.2% |
| q16 | 164.1 | 8.8% |
| q07 | 134.0 | 7.2% |
| q03 | 130.5 | 7.0% |
| q05 | 123.8 | 6.6% |
| q08 | 110.0 | 5.9% |
| q04 | 100.0 | 5.3% |
| q22 | 95.3 | 5.1% |
| q17 | 87.7 | 4.7% |
| q14 | 85.7 | 4.6% |
| q19 | 83.7 | 4.5% |
| q02 | 53.6 | 2.9% |

## Plans with operator timings (slowest templates)

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
│           0.03s           │
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
│           0.01s           │                                                                                       │          (0.00s)          │              │
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
│           0.88s           ├──────────────┐                                                                        │        s_nationkey        ││           n_name          │
│                           │              │                                                                        │                           ││                           │
│                           │              │                                                                        │      Dynamic Filters:     ││                           │
│                           │              │                                                                        │  optional: s_nationkey>=0 ││                           │
│                           │              │                                                                  
... (truncated)
```

### q13.m0

```sql
SELECT c_count, count(*) AS custdist FROM ( SELECT c_custkey, count(o_orderkey) FROM customer LEFT OUTER JOIN orders ON c_custkey = o_custkey AND o_comment NOT LIKE '%unusual%packages%' GROUP BY c_custkey) AS c_orders (c_custkey, c_count) GROUP BY c_count ORDER BY custdist DESC, c_count DESC
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.300s              ││
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
│           0.05s           │
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
│     Large Table: true     │
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
│           0.22s           │
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
│           0.25s           │              │
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
│           0.01s           ││          (0.00s)          │
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
│      Dynamic Filters:     ││                           │
│ optional: o_custkey>=1 AND││                           │
│    optional: o_custkey<   ││                           │
│          =1500000         ││                           │
│                           ││                           │
│                           ││                           │
│                           ││                           │
│      14,833,270 rows      ││       1,500,000 rows      │
│           1.12s           ││          (0.01s)          │
└───────────────────────────┘└───────────────────────────┘
```

### q18.m0

```sql
SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS sum_qty FROM customer, orders, lineitem WHERE o_orderkey IN (SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 312) AND c_custkey = o_custkey AND o_orderkey = l_orderkey GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice ORDER BY o_totalprice DESC, o_orderdate, o_orderkey LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.258s              ││
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
│__internal_compress_integra│
│     l_uinteger(#3, 1)     │
│             #4            │
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
│__internal_decompress_integ│
│     ral_bigint(#3, 1)     │
│             #4            │
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
│           0.06s           │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         PROJECTION        ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│__internal_compress_integra││__internal_compress_integra│
│     l_uinteger(#0, 1)     ││     l_uinteger(#0, 1)     │
│             #1            ││             #1            │
│                           ││__internal_compress_integra│
│                           ││     l_uinteger(#2, 1)     │
│                           ││             #3            │
│                           ││             #4            │
│           0.01s           ││                           │
│                           ││                           │
│                           ││                           │
│      12,130,926 rows      ││          111 rows         │
│          (0.01s)          ││           0.00s           │
└─────────────┬─────────────┘└─────────────┬─────────────┘
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         TABLE_SCAN        ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│           Table:          ││__internal_decompress_integ│
│   "tpch-main-sf10".main   ││     ral_bigint(#0, 1)     │
│         .lineitem         ││             #1            │
│                           ││__internal_decompress_integ│
│   Type: Sequential Scan   ││     ral_bigint(#2, 1)     │
│                           ││             #3            │
│        Projections:       ││             #4            │
│         l_orderkey        ││                           │
│         l_quantity        ││                           │
│                           ││                           │
│      Dynamic Filters:     ││                           │
│    optional: l_orderkey   ││           0.00s           │
│   =1263015 OR l_orderkey  ││                           │
│   =1544643 OR l_orderkey  ││                           │
│   =2199712 OR l_orderkey  ││                           │
│   =2869152 OR l_orderkey  ││                           │
│   =2942469 OR l_orderkey  ││                           │
│   =3043270 OR l_orderkey  ││                           │
│   =3767271 OR l_orderkey  ││                           │
│   =4702759 OR l_orderkey  ││                           │
│   =4722021 OR l_orderkey  ││                           │
│   =4806726 OR l_orderkey  ││                           │
│   =7062629 OR l_orderkey  ││                           │
│   =7235014 OR l_orderkey  ││                           │
│   =7549735 OR l_orderkey  ││                           │
│   =7810823 OR l_orderkey  ││                           │
│   =8075589 OR l_orderkey  ││                           │
│   =9506693 OR l_orderkey  ││                           │
│  =10408580 OR l_orderkey  ││                           │
│  =10612710 OR l_orderkey  ││                           │
│  =10805828 OR l_orderkey  ││                           │
│  =11141606 OR l_orderkey  ││                           │
│  =11599171 OR l_orderkey  ││                           │
│  =12314084 OR l_orderkey  ││                           │
│  =12378086 OR l_orderkey  ││                           │
│  =12809282 OR l_orderkey  ││                           │
│  =13165024 OR l_orderkey  ││                           │
│  =13683589 OR l_orderkey  ││                           │
│  =13837220 OR l_orderkey  ││                           │
│  =15071267 OR l_orderkey  ││                           │
│  =17366275 OR l_orderkey  ││                           │
│  =17457767 OR l_orderkey  ││                           │
│  =17927718 OR l_orderkey  ││                           │
│  =18449123 OR l_orderkey  ││                           │
│  =19217698 OR l_orderkey  ││                           │
│  =19628135 OR l_orderkey  ││                           │
│  =20324257 OR l_orderkey  ││                           │
│  =20649506 OR l_orderkey  ││                           │
│  =20662370 OR l_orderkey  ││                           │
│  =20971013 OR l_orderkey  ││                           │
│  =21135524 OR l_orderkey  ││                           │
│  =21213895 OR l_orderkey  ││                           │
│  =22017989 OR l_orderkey  ││                           │
│  =23245603 OR l_orderkey  ││                           │
│  =23861472 OR l_orderkey  ││                           │
│  =23906277 OR l_orderkey  ││                           │
│  =24378656 OR l_orderkey  ││                           │
│  =24923202 OR l_orderkey  ││                           │
│  =25243237 OR l_orderkey  ││                           │
│  =26465922 OR l_orderkey  ││                           │
│  =26471747 OR l_orderkey  ││                           │
│  =26977863 OR l_orderkey  ││                           │
│  =28077922 OR l_orderkey  ││                           │
│  =28184576 OR l_orderkey  ││                           │
│  =29122912 OR l_orderkey  ││                           │
│  =29294434 OR l_orderkey  ││                           │
│  =29326886 OR l_orderkey  ││                           │
│  =32393895 OR l_orderkey  ││                           │
│  =32624836 OR l_orderkey  ││                           │
│  =33615872 OR l_orderkey  ││                           │
│  =34201984 OR l_orderkey  ││                           │
│  =34472643 OR l_orderkey  ││                           │
│  =34509573 OR l_orderkey  ││                           │
│  =34937604 OR l_orderkey  ││                           │
│  =35383045 OR l_orderkey  ││                           │
│  =35542498 OR l_orderkey  ││                           │
│  =36327201 OR l_orderkey  ││                           │
│  =36667107 OR l_orderkey  ││                           │
│  =37531878 OR l_orderkey  ││                           │
│  =38914978 OR l_orderkey  ││                           │
│  =39492870 OR l_orderkey  ││                           │
│  =39702437 OR l_or
... (truncated)
```

### q16.m0

```sql
SELECT p_brand, p_type, p_size, count(DISTINCT ps_suppkey) AS supplier_cnt FROM partsupp, part WHERE p_partkey = ps_partkey AND p_brand <> 'Brand#51' AND p_type NOT LIKE 'MEDIUM PLATED%' AND p_size IN (29, 2, 23, 11, 13, 1, 46, 40) AND ps_suppkey NOT IN (SELECT s_suppkey FROM supplier WHERE s_comment LIKE '%Customer%Complaints%') GROUP BY p_brand, p_type, p_size ORDER BY supplier_cnt DESC, p_brand, p_type, p_size
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.138s              ││
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
│           0.28s           │
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
│       1,185,556 rows      │                                                                        │
│           0.01s           │                                                                        │
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
│           0.10s           │              │                                           │                           │
│                           │              │                                           │          Filters:         │
│                           │              │                                           │  (s_comment ~~ '%Customer │
│                           │              │                                           │       %Complaints%')      │
│                           │              │                                           │                           │
│                           │              │                                           │                           │
│                           │              │                                           │                           │
│       1,185,556 rows      │              │                                           │          56 rows          │
│          (0.10s)          │              │                                           │           0.01s           │
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
│           0.05s           ││          (0.00s)          │
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
