# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 556.0 ms, total 556 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q18 | 556.0 | 100.0% |

## Plans with operator timings (slowest templates)

### q18.m0

```sql
SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS sum_qty FROM customer, orders, lineitem WHERE o_orderkey IN (SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 312) AND c_custkey = o_custkey AND o_orderkey = l_orderkey GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice ORDER BY o_totalprice DESC, o_orderdate, o_orderkey LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.736s              ││
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
│           0.08s           │              │
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
│           0.01s           ││                           │
│                           ││                           │
│                           ││                           │
│      17,537,646 rows      ││          111 rows         │
│          (0.01s)          ││           0.00s           │
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
│      Dynamic Filters:     ││           0.00s           │
│   optional: l_orderkey>   ││                           │
│  =1263015 AND l_orderkey< ││                           │
│   =1544643 OR l_orderkey  ││                           │
│  =2199712 OR l_orderkey>  ││                           │
│  =2869152 AND l_orderkey< ││                           │
│   =3043270 OR l_orderkey  ││                           │
│  =3767271 OR l_orderkey>  ││                           │
│  =4702759 AND l_orderkey< ││                           │
│  =4806726 OR l_orderkey>  ││                           │
│  =7062629 AND l_orderkey< ││                           │
│   =8075589 OR l_orderkey  ││                           │
│  =9506693 OR l_orderkey>  ││                           │
│ =10408580 AND l_orderkey< ││                           │
│  =11599171 OR l_orderkey> ││                           │
│ =12314084 AND l_orderkey< ││                           │
│  =13165024 OR l_orderkey> ││                           │
│ =13683589 AND l_orderkey< ││                           │
│  =13837220 OR l_orderkey  ││                           │
│  =15071267 OR l_orderkey> ││                           │
│ =17366275 AND l_orderkey< ││                           │
│  =17457767 OR l_orderkey  ││                           │
│  =17927718 OR l_orderkey  ││                           │
│  =18449123 OR l_orderkey> ││                           │
│ =19217698 AND l_orderkey< ││                           │
│  =19628135 OR l_orderkey> ││                           │
│ =20324257 AND l_orderkey< ││                           │
│  =21213895 OR l_orderkey  ││                           │
│  =22017989 OR l_orderkey  ││                           │
│  =23245603 OR l_orderkey> ││                           │
│ =23861472 AND l_orderkey< ││                           │
│  =23906277 OR l_orderkey  ││                           │
│  =24378656 OR l_orderkey> ││                           │
│ =24923202 AND l_orderkey< ││                           │
│  =25243237 OR l_orderkey> ││                           │
│ =26465922 AND l_orderkey< ││                           │
│  =26471747 OR l_orderkey  ││                           │
│  =26977863 OR l_orderkey> ││                           │
│ =28077922 AND l_orderkey< ││                           │
│  =28184576 OR l_orderkey> ││                           │
│ =29122912 AND l_orderkey< ││                           │
│  =29326886 OR l_orderkey> ││                           │
│ =32393895 AND l_orderkey< ││                           │
│  =32624836 OR l_orderkey  ││                           │
│  =33615872 OR l_orderkey> ││                           │
│ =34201984 AND l_orderkey< ││                           │
│  =35542498 OR l_orderkey> ││                           │
│ =36327201 AND l_orderkey< ││                           │
│  =36667107 OR l_orderkey  ││                           │
│  =37531878 OR l_orderkey  ││                           │
│  =38914978 OR l_orderkey> ││                           │
│ =39492870 AND l_orderkey< ││                           │
│  =39702437 OR l_orderkey  ││                           │
│  =40356833 OR l_orderkey> ││                           │
│ =40876003 AND l_orderkey< ││                           │
│  =41277440 OR l_orderkey> ││                           │
│ =42262528 AND l_orderkey< ││                           │
│  =42290181 OR l_orderkey> ││                           │
│ =42997059 AND l_orderkey< ││                           │
│  =44257860 OR l_orderkey  ││                           │
│  =45897379 OR l_orderkey> ││                           │
│ =46486080 AND l_orderkey< ││                           │
│  =46794464 OR l_orderkey> ││                           │
│ =48300454 AND l_orderkey< ││                           │
│  =48395044 OR l_orderkey> ││                           │
│ =48881602 AND l_orderkey< ││                           │
│  =48943904 OR l_orderkey> ││                           │
│ =49474597 AND l_orderkey< ││                           │
│  =49847329 OR l_orderkey> ││                           │
│ =51063047 AND l_orderkey< ││                           │
│  =51532000 OR l_orderkey  ││                           │
│  =52340710 OR l_or
... (truncated)
```
