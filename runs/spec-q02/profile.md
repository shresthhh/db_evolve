# Profile of the current best build

Visible templates, hot runs, 8 threads. Geomean 51.6 ms, total 52 ms.

| Template | Time (ms) | Share of total |
| --- | ---: | ---: |
| q02 | 51.6 | 100.0% |

## Plans with operator timings (slowest templates)

### q02.m0

```sql
SELECT s_acctbal, s_name, n_name, p_partkey, p_mfgr, s_address, s_phone, s_comment FROM part, supplier, partsupp, nation, region WHERE p_partkey = ps_partkey AND s_suppkey = ps_suppkey AND p_size = 1 AND p_type LIKE '%STEEL' AND s_nationkey = n_nationkey AND n_regionkey = r_regionkey AND r_name = 'AMERICA' AND ps_supplycost = ( SELECT min(ps_supplycost) FROM partsupp, supplier, nation, region WHERE p_partkey = ps_partkey AND s_suppkey = ps_suppkey AND s_nationkey = n_nationkey AND n_regionkey = r_regionkey AND r_name = 'AMERICA') ORDER BY s_acctbal DESC, n_name, s_name, p_partkey LIMIT 100
```

```
┌────────────────────────────────────────────────┐
│┌──────────────────────────────────────────────┐│
││              Total Time: 0.0862s             ││
│└──────────────────────────────────────────────┘│
└────────────────────────────────────────────────┘
┌───────────────────┐
│       QUERY       │
└─────────┬─────────┘
┌─────────┴─────────┐
│  EXPLAIN_ANALYZE  │
│    ────────────   │
│                   │
│       0 rows      │
│       0.00s       │
└─────────┬─────────┘
┌─────────┴─────────┐
│       TOP_N       │
│    ────────────   │
│      Top: 100     │
│                   │
│     Order By:     │
│  "tpch-main-sf10" │
│   .main.supplier  │
│  .s_acctbal DESC  │
│  "tpch-main-sf10" │
│    .main.nation   │
│    .n_name ASC    │
│  "tpch-main-sf10" │
│   .main.supplier  │
│    .s_name ASC    │
│  "tpch-main-sf10" │
│     .main.part    │
│   .p_partkey ASC  │
│                   │
│                   │
│                   │
│      100 rows     │
│       0.00s       │
└─────────┬─────────┘
┌─────────┴─────────┐
│     PROJECTION    │
│    ────────────   │
│     s_acctbal     │
│       s_name      │
│       n_name      │
│     p_partkey     │
│       p_mfgr      │
│     s_address     │
│      s_phone      │
│     s_comment     │
│                   │
│                   │
│                   │
│     4,816 rows    │
│       0.00s       │
└─────────┬─────────┘
┌─────────┴─────────┐
│     PROJECTION    │
│    ────────────   │
│         #3        │
│         #4        │
│         #7        │
│         #8        │
│         #9        │
│        #10        │
│        #11        │
│        #14        │
│                   │
│                   │
│                   │
│     4,816 rows    │
│       0.00s       │
└─────────┬─────────┘
┌─────────┴─────────┐
│       FILTER      │
│    ────────────   │
│  (ps_supplycost = │
│      SUBQUERY)    │
│                   │
│                   │
│                   │
│     4,816 rows    │
│       0.00s       │
└─────────┬─────────┘
┌─────────┴─────────┐
│        CTE        │
│    ────────────   │
│     CTE Name:     │
│ __common_subplan_1│
│                   │
│    Table Index:   │
│         23        ├────────────────────────────────────────────────────┐
│                   │                                                    │
│                   │                                                    │
│                   │                                                    │
│       0 rows      │                                                    │
│       0.01s       │                                                    │
└─────────┬─────────┘                                                    │
┌─────────┴─────────┐                                          ┌─────────┴─────────┐
│     HASH_JOIN     │                                          │  LEFT_DELIM_JOIN  │
│    ────────────   │                                          │    ────────────   │
│     Join Type:    │                                          │     Join Type:    │
│       INNER       │                                          │        LEFT       │
│                   │                                          │                   │
│    Conditions:    │                                          │    Conditions:    │
│   s_nationkey =   │                                          │  p_partkey IS NOT │
│     n_nationkey   │                                          │    DISTINCT FROM  │
│                   ├──────────┐                               │      p_partkey    ├────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────┐
│                   │          │                               │                   │                                                    │                                                                                   │
│                   │          │                               │    Delim Index:   │                                                    │                                                                                   │
│                   │          │                               │         1         │                                                    │                                                                                   │
│       0.00s       │          │                               │                   │                                                    │                                                                                   │
│                   │          │                               │                   │                                                    │                                                                                   │
│                   │          │                               │                   │                                                    │                                                                                   │
│    20,051 rows    │          │                               │       0 rows      │                                                    │                                                                                   │
│      (0.00s)      │          │                               │       0.01s       │                                                    │                                                                                   │
└─────────┬─────────┘          │                               └─────────┬─────────┘                                                    │                                                                                   │
┌─────────┴─────────┐┌─────────┴─────────┐                     ┌─────────┴─────────┐                                          ┌─────────┴─────────┐                                                               ┌─────────┴─────────┐
│     TABLE_SCAN    ││     HASH_JOIN     │                     │     HASH_JOIN     │                                          │     HASH_JOIN     │                                                               │   HASH_GROUP_BY   │
│    ────────────   ││    ────────────   │                     │    ────────────   │                                          │    ────────────   │                                                               │    ────────────   │
│       Table:      ││     Join Type:    │                     │     Join Type:    │                                          │     Join Type:    │                                                               │     Groups: #3    │
│  "tpch-main-sf10" ││       INNER       │                     │       INNER       │                                          │        LEFT       │                                                               │                   │
│   .main.supplier  ││                   │                     │                   │                                          │                   │                                                               │                   │
│                   ││    Conditions:    │                     │    Conditions:    │                                          │    Conditions:    │                                                               │                   │
│       Type:       ││   n_regionkey =   │                     │    ps_suppkey =   │                                          │  p_partkey IS NOT │                                                               │                   │
│  Sequential Scan  ││     r_regionkey   │                     │      s_suppkey    │                                          │    DISTINCT FROM  │                                                               │       0.00s       │
│                   ││                   │                     │                   │                                          │      p_partkey    │                                                               │                   │
│    Projections:   ││                   │                     │                   │                                          │                   │                                                               │                   │
│     s_suppkey     ││                   │                     │                   │                                          │                   │                                                               │                   │
│    s_nationkey    ││                   │                     │                   │                                          │                   │                                                               │                   │
│     s_acctbal     ││       0.00s       │                     │       0.01s       │                                          │                   │                                                               │                   │
│       s_name      ││                   │                     │                   │                                          │       0.00s       │                                                               │                   │
│     s_address     ││                   │                     │                   │                                          │                   │                                                               │                   │
│      s_phone      ││                   ├──────────┐          │                   ├───────────────────────────────┐          │                   ├──────────┐                                                    │                   │
│     s_comment     ││                   │          │          │                   │                               │          │                   │          │                                                    │                   │
│                   ││                   │          │          │                   │                               │          │                   │          │         
... (truncated)
```
