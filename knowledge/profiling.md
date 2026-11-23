# Finding where the time goes

Work from measurements. The tool is `dbe-tool` (full path in your instructions).

## Per-template timings

`dbe-tool bench` prints, for each visible template, the current best build's time, your build's
time and the ratio. `.dbe/profile.md` has the same numbers for the current best, ranked by share
of total time. A template that takes 30 % of the total is worth ten that take 1 %.

The objective is a geometric mean, so a 20 % gain on a 5 ms template counts as much as a 20 %
gain on a 500 ms one. Short templates are dominated by fixed costs (parsing, binding,
optimization, task startup, result rendering); long ones by operators.

## Per-operator timings

`dbe-tool profile q06.m0` runs `EXPLAIN ANALYZE` on your build and prints the plan with the time
and row count of every operator. Read it for:

- the operator with the largest time: that is the first suspect;
- row counts that collapse late: a filter or join that could have run earlier;
- estimated versus actual cardinality: a bad estimate upstream of a bad join order;
- operators that process far more rows than they emit.

Timings in a parallel plan are summed over threads, so they can exceed wall time.

## Checking a hypothesis cheaply

`dbe-tool sql "<statement>"` runs any statement on your build against the benchmark database. Use
it to isolate a cost before writing code:

- strip a query down to one operator (`SELECT count(*) FROM t WHERE ...`) to time a scan or filter
  on its own;
- compare two formulations of the same query to see what a rewrite would buy;
- `SET threads = 1` first to separate per-row cost from scheduling effects;
- `PRAGMA disabled_optimizers = '...'` to learn what a pass currently contributes.

If an isolated experiment does not show the cost you expected, the idea is probably wrong. Say so
and stop; that result is worth recording.

## Noise

Single runs vary by a few percent. `dbe-tool bench` takes the median of several hot runs, but
differences under about 5 % are not evidence. The harness makes the final call with interleaved
runs and a bar set from a measured noise floor.
