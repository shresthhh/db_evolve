# Optimization playbook

Directions that have paid off in analytical engines, roughly from cheapest to most invasive. None
is guaranteed to apply; check the profile first. Each must be expressed as a general rule.

## Do less work

- Stop early. LIMIT without ORDER BY, EXISTS, semi and anti joins, and top-N can often terminate
  or prune once the answer is determined.
- Skip data. Zone maps and min/max statistics, dynamic filters pushed from a join's build side or
  from a top-N heap into the scan, row-group pruning.
- Push filters and projections down; materialise wide or string columns late.
- Evaluate cheap, selective predicates first; avoid re-evaluating common sub-expressions.
- Rewrite at plan time: simplify expressions over constants, turn correlated subqueries into
  joins or aggregates, share common sub-plans, remove redundant grouping keys, pick the smaller
  join build side.

## Do the same work on cheaper representations

- Operate on dictionary codes instead of strings for filters, group keys and join keys; decode
  once per dictionary, not once per row.
- Group or join on narrow integers when statistics prove the domain is small (perfect hash
  tables, direct array aggregation).
- Keep data compressed through operators where the operation commutes with the encoding.
- Avoid copying strings and rows between operators when a reference is safe.

## Make the inner loop cheaper

- Remove per-row branches, virtual calls and allocations; hoist invariants; specialise the hot
  type combinations that the generic path handles slowly.
- Help the compiler vectorise: tight loops over flat arrays, no aliasing, no hidden control flow.
- Improve cache behaviour: partition before building large hash tables, prefetch on probe, keep
  hot state compact.
- Fast paths for the common case (no NULLs, constant or flat vectors, single key) with the
  generic path as fallback.

## Use the hardware

- Parallelise phases that still run on one thread (finalisation, merging, materialisation).
- Reduce contention: per-thread state, fewer shared atomics and locks on hot paths.
- Balance work across threads when morsels are skewed.

## Fixed costs (matter for short queries)

- Planning and optimization passes that run regardless of need; repeated catalog lookups; task
  scheduling overhead for tiny inputs; result materialisation and conversion.

## How ideas fail

- The cost was not where it seemed: profile again before coding.
- The fast path's conditions are rarer than expected: measure how often it triggers.
- A gain on one template is paid for by another: run the whole visible set, not just the target.
- The gain is real but below noise: combine with a related change, or retire it and move on.
