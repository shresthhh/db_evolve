# Rules for every change

These hold for all agents. The harness enforces most of them mechanically; the reviewer enforces
the rest.

## What counts as an improvement

A change is accepted only if it makes the engine faster for a *class* of queries, stated without
reference to this benchmark. "Hash aggregation with a LIMIT and no ORDER BY can stop admitting new
groups" is a class. "The query that filters on ship date" is not.

A useful test: describe the change to someone who has never seen the workload. If the description
still makes sense and they could name other queries it helps, it is general.

## Never

1. Recognise the workload. No table names, column names, literals, row counts, scale factors or
   data distributions from the benchmark in engine code, comments or tests.
2. Cache answers. No result, plan or intermediate caches keyed on query text or on anything that
   only repeats because a benchmark runs the same statement several times. (Caches a real system
   would keep, such as decoded dictionaries or metadata, are fine when they are bounded,
   invalidated correctly, and pay off for workloads that are not repetitions of one query.)
3. Move cost out of sight. Do not make queries faster by doing proportional work at load time or
   startup, by using more threads or memory than the user configured, or by skipping checks that
   protect correctness or durability.
4. Touch measurement. The shell, timing, output formatting, default settings, tests and benchmark
   directories are off limits.
5. Trade correctness for speed. Results must be identical to the original engine's for every
   input, including the ones no test here exercises.

## Always

1. One idea per change. Small diffs are reviewed faster and bisect cleanly.
2. Guard fast paths. State the exact conditions under which the fast path is valid and fall back
   to the existing code otherwise. Think about NULLs, empty input, overflow, all types the
   operator accepts, parallelism and out-of-memory spilling.
3. Measure. A change with no measured effect is retired, however elegant.
4. Leave a record. Say what you tried, what you measured and why you stopped. Failed experiments
   are as valuable to the next agent as successful ones.
