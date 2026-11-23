# Memory

## Workload
- Single visible template q01 = TPC-H Q1 shape: scan lineitem with one range filter on a date (selects ~98%),
  4 groups (2 string keys -> compressed to utinyint), 4 sum_no_overflow + 3 avg + count_star on DECIMAL(int64).
- Bench ~298ms after E0005 (profile). Operator CPU: TABLE_SCAN 2.09s, PERFECT_HASH_GROUP_BY 1.13s,
  projections 0.19 + 0.04 + 0.18s.
- Storage: l_quantity/extendedprice/discount/tax/shipdate = BitPacking (FOR mode); returnflag/linestatus = old Dictionary.
- Group distribution: N,O 49%, A,F 25%, R,F 25%, N,F <1%, randomly interleaved.

## Key measurements (dbe-tool sql EXPLAIN ANALYZE, single runs, noisy)
- sum(l_quantity) alone: wall 0.102s, scan CPU 0.67s (~11ns/value!). sum(l_extendedprice): 0.150s, scan 1.07s.
  4 decimal sums, no filter: 0.291s wall, scan 2.04s. Wider bit width -> slower. Unexplained: unpack should be ~1ns/value.
  Not yet known whether this is the machine (WSL2, maybe oversubscribed threads) or the code. Next step: threads=1 vs 8.
- Q1 with filter ~680ms vs no filter + max(shipdate) ~555ms in early rounds; the filter column scan is ~60-70ms of it.
- count(*) with only the date filter: 71ms.
- Decimal multiply already drops its overflow check via stats (arithmetic.cpp PropagateNumericStats ~l.174-184),
  so the projections are not doing overflow checks.

## Codebase facts
- Scan with filters: RowGroup::Scan (src/storage/table/row_group.cpp ~694-829). Filter cols -> ColumnData::Filter
  (Scan + ToUnifiedFormat + FilterSelection). Other cols -> compression select, else Scan + Slice(sel).
- ColumnData::ScanVector / GetVectorScanType / FetchUpdates take update_lock per vector (column_data.cpp:54, 121, 266).
- Bitpacking scan: BitpackingScanPartial (bitpacking.cpp:775). Per 32 values: UnPackBlock (switch on width ->
  fastpforlib Unroller, scalar) + ApplyFrameOfReference pass. No bitpacking filter/select callbacks.
- Perfect hash agg: src/execution/perfect_aggregate_hashtable.cpp. MAX_REPLICA_COUNT l.10, MAX_REPLICATED_HT_SIZE 1MiB l.12,
  replica choice l.36-45 (falls to 1 if 4x does not fit), replica mask l.312 (needs a power of two). E0005 typed fused loops in AddChunk.
- sum_no_overflow: extension/core_functions/aggregate/distributive/sum.cpp. avg stats rewrite: avg.cpp (E0004).
- dbe-tool sql: typeof(col) needs an aggregate wrapper. EXPLAIN ANALYZE works; pipe through grep is allowed.
  Read the .dbe files with the Read tool (cd plus head is blocked).

## Round log
- G1R1: E0001 per-group simple_update -> RETIRED (bad idea: groups interleaved).
- G1R2: E0002 bitpacking select (flat compacted payload) -> RETIRED: neutral. Slicing is not the cost.
- G1R3: E0003 perfect HT replicas K=4 -> ACCEPTED -12.3%.
- G1R4: E0004 avg int64 state via stats -> ACCEPTED -5.1%.
- G1R5: E0005 fused typed update loops for sum/avg/count_star in perfect HT -> ACCEPTED -5.9% (1.277x).
  Row-wise fusion (all aggregates per row, with a switch) was 34% SLOWER; keep column-at-a-time typed loops.
- G1R6: dispatched K=8 replicas with a halving fallback to fit the 1MiB cap.

## Directions
- Promising: perfect-HT micro-work (replicas, typed loops) gave reliable wins. Extending the E0005 fast path to
  count(x), min/max, double sum/avg would generalise it (more aggregate mixes take the fast path).
- Biggest open target: the scan at 11-18ns/value for bitpacked int64 (see the investigation issue). Measure before coding.
- Fuse stacked projections (0.4s CPU): needs optimizer investigation (compressed_materialization).
- Exhausted: per-group partitioning (E0001), flat select output (E0002), decimal overflow checks (already removed by stats).
