# DuckDB codebase map (v1.5.x)

A starting map, not a specification. Verify a path or function exists before relying on it;
headers mirror sources under `src/include/duckdb/`.

## Life of a query

parser (`src/parser`) -> binder and logical plan (`src/planner`) -> optimizer (`src/optimizer`) ->
physical plan (`src/execution/physical_plan`) -> pipelines and tasks (`src/parallel`) ->
operators (`src/execution/operator`) reading from storage (`src/storage`).

Execution is vectorised and push-based. Operators exchange `DataChunk`s of up to 2048 rows made
of `Vector`s (flat, constant, dictionary or sequence), with selection vectors and validity masks
(`src/common/types`, `src/common/vector_operations`). A pipeline runs from a source through
streaming operators into a sink; sinks keep per-thread local state and combine at the end.

## Where time usually goes in analytical queries

| Area | Code |
| --- | --- |
| Table scans, zone maps, filter pushdown into scans | `src/storage/table`, `src/function/table/table_scan.cpp`, `src/execution/operator/scan` |
| Column compression and decompression (dictionary, FSST, bit-packing, RLE, ALP) | `src/storage/compression` |
| Filters and expression evaluation | `src/execution/expression_executor*`, `src/execution/adaptive_filter.cpp`, `src/function/scalar` |
| Hash joins (build, probe, bloom/perfect-hash variants) | `src/execution/join_hashtable.cpp`, `src/execution/operator/join` |
| Hash aggregation (radix-partitioned, perfect) | `src/execution/aggregate_hashtable.cpp`, `radix_partitioned_hashtable.cpp`, `perfect_aggregate_hashtable.cpp`, `src/execution/operator/aggregate` |
| Aggregate and window function kernels | `src/function/aggregate`, `src/function/window`, `extension/core_functions` |
| Sorting and top-N | `src/common/sort`, `src/execution/operator/order` |
| Row layouts used by joins, aggregates, sorts | `src/common/types/row`, `src/common/row_operations` |
| Hashing | `src/common/types/hash.cpp`, `src/common/vector_operations` |
| String handling (`string_t`, LIKE, substring) | `src/common/types/string_type.cpp`, `src/function/scalar/string` |
| Task scheduling and pipeline execution | `src/parallel` |

## Optimizer

`src/optimizer/optimizer.cpp` lists the passes in order. Relevant ones: filter pushdown and
pullup, join order (`join_order/`), statistics propagation (`statistics/`), build/probe side
selection, join filter pushdown, top-N, late materialization, common sub-expression and common
aggregate elimination, compressed materialization, IN-clause rewriting, expression rewrite rules
(`rule/`). A missed rewrite here often beats micro-optimising an operator.

## Reading plans

- In `HASH_JOIN`, the **left child is the probe side and the right child is the build side**. Check
  this before proposing a "wrong build side" fix; a pilot experiment lost a round on it.
- Filters a join pushes into the probe-side scan appear under the scan as dynamic filters
  (min/max ranges, and sometimes a bloom filter shown as `IN BF`).
- Operator times in `EXPLAIN ANALYZE` are summed over threads.

## Practical notes

- Editing a widely included header rebuilds much of the engine (10 to 15 minutes); editing a
  `.cpp` file rebuilds one unity unit (a minute or two).

- The build is a unity build: several `.cpp` files compile as one translation unit per directory.
  New files must be listed in that directory's `CMakeLists.txt`.
- `extension/core_functions` holds most scalar and aggregate functions that are not in `src/function`.
- Generated files (function lists, serialization) are marked as such at the top; do not hand-edit
  them unless you also keep them consistent.
- Settings live in `src/main/settings`. Changing a default is not an optimization.
