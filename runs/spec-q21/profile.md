# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 1096.9 ms, total 1097 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q21 | 1096.9 | 100.0% |

## Plans with operator timings (slowest templates)

### q21.m0

```sql
SELECT s_name, count(*) AS numwait FROM supplier, lineitem l1, orders, nation WHERE s_suppkey = l1.l_suppkey AND o_orderkey = l1.l_orderkey AND o_orderstatus = 'F' AND l1.l_receiptdate > l1.l_commitdate AND EXISTS (SELECT * FROM lineitem l2 WHERE l2.l_orderkey = l1.l_orderkey AND l2.l_suppkey <> l1.l_suppkey) AND NOT EXISTS (SELECT * FROM lineitem l3 WHERE l3.l_orderkey = l1.l_orderkey AND l3.l_suppkey <> l1.l_suppkey AND l3.l_receiptdate > l3.l_commitdate) AND s_nationkey = n_nationkey AND n_name = 'JAPAN' GROUP BY s_name ORDER BY numwait DESC, s_name LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││               Total Time: 1.08s              ││
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
│      0.02s      │
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
│                 │                                                                  │                                                        │         │      0.33s      │         │                            │                 │
│                 │                                                                  │                                                        │         │                 │         │                            │                 │
│      0 rows     │                                                                  │                                                        │         │   40,074 rows   │         │                            │   708,431 rows  │
│      0.33s      │                                                                  │                                                        │         │     (0.33s)     │         │                            │     (0.03s)     │
└────────┬────────┘                                                                  │                                                        │         └────────┬────────┘         │                            └─────────────────┘
┌────────┴────────┐                                                         ┌────────┴────────┐                                      ┌────────┴────────┐┌────────┴────────┐┌────────┴────────┐
│    HASH_JOIN    │                                                         │    HASH_JOIN    │                                      │  HASH_GROUP_BY  ││ COLUMN_DATA_SCAN││    PROJECTION   │
│    ──────────   │                                                         │    ──────────   │                                      │    ──────────   ││                 ││    ──────────   │
│    Join Type:   │                                                         │    Join Type:   │                                      │     Groups:     ││                 ││    l_suppkey    │
│      INNER      │                                                         │    RIGHT_SEMI   │                                      │        #2       ││      0.00s      ││    l_orderkey   │
│                 │                                                         │                 │                                     
... (truncated)
```
