# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 40.6 ms, total 658 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q09 | 116.6 | 17.7% |
| q13 | 98.2 | 14.9% |
| q18 | 81.6 | 12.4% |
| q16 | 43.3 | 6.6% |
| q19 | 42.8 | 6.5% |
| q22 | 39.9 | 6.1% |
| q03 | 37.7 | 5.7% |
| q07 | 34.7 | 5.3% |
| q05 | 34.3 | 5.2% |
| q04 | 31.6 | 4.8% |
| q08 | 29.6 | 4.5% |
| q14 | 24.5 | 3.7% |
| q02 | 22.3 | 3.4% |
| q17 | 20.7 | 3.2% |

## Plans with operator timings (slowest templates)

### q09.m0

```sql
SELECT nation, o_year, sum(amount) AS sum_profit FROM ( SELECT n_name AS nation, extract(year FROM o_orderdate) AS o_year, l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity AS amount FROM part, supplier, lineitem, partsupp, orders, nation WHERE s_suppkey = l_suppkey AND ps_suppkey = l_suppkey AND ps_partkey = l_partkey AND p_partkey = l_partkey AND o_orderkey = l_orderkey AND s_nationkey = n_nationkey AND p_name LIKE '%ghost%') AS profit GROUP BY nation, o_year ORDER BY nation, o_year DESC
```

```
└───────────────────────────┘└───────────────────────────┘
```

### q13.m0

```sql
SELECT c_count, count(*) AS custdist FROM ( SELECT c_custkey, count(o_orderkey) FROM customer LEFT OUTER JOIN orders ON c_custkey = o_custkey AND o_comment NOT LIKE '%unusual%packages%' GROUP BY c_custkey) AS c_orders (c_custkey, c_count) GROUP BY c_count ORDER BY custdist DESC, c_count DESC
```

```
└───────────────────────────┘└───────────────────────────┘
```

### q18.m0

```sql
SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS sum_qty FROM customer, orders, lineitem WHERE o_orderkey IN (SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 312) AND c_custkey = o_custkey AND o_orderkey = l_orderkey GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice ORDER BY o_totalprice DESC, o_orderdate, o_orderkey LIMIT 100
```

```
                                                          └───────────────────────────┘
```

### q16.m0

```sql
SELECT p_brand, p_type, p_size, count(DISTINCT ps_suppkey) AS supplier_cnt FROM partsupp, part WHERE p_partkey = ps_partkey AND p_brand <> 'Brand#51' AND p_type NOT LIKE 'MEDIUM PLATED%' AND p_size IN (29, 2, 23, 11, 13, 1, 46, 40) AND ps_suppkey NOT IN (SELECT s_suppkey FROM supplier WHERE s_comment LIKE '%Customer%Complaints%') GROUP BY p_brand, p_type, p_size ORDER BY supplier_cnt DESC, p_brand, p_type, p_size
```

```
                             └───────────────────────────┘└───────────────────────────┘
```
