# Related work, and what db_evolve takes from it

Notes on the four papers in this folder and the Intent Lab post. Numbers are as the sources
report them.

## Intent Lab: an agent fleet on ClickBench

<https://intentlab.ai/blog/an-agent-fleet-on-clickbench>

The closest thing to this project: agents improved an existing codebase (GizmoSQL, with DuckDB
inside it) over 25 days and took first place on ClickBench's combined score.

- **Loop.** Each experiment starts with a design that states the change and the bar it must
  clear. Other agents review the design, another builds it. A build that passes the gates is
  timed against the best build, with runs alternating on one machine. It becomes the new best or
  is retired with a written reason. Design, results and reason go into a shared record that later
  proposals read first.
- **Bar.** Faster over the 43 queries in both run orders; no query slower by more than 5 % or
  10 ms, whichever is larger. Gates: same answers as the original, unusual inputs, a memory checker.
- **Anti-gaming.** Before each submission, independent reviewer agents read every source change
  for anything that helps only the benchmark. They removed a matcher for one query's exact regular
  expression, a cross-run result cache, lists naming particular columns or queries, and a
  load-time index answering two queries. Keeping those would have been up to 5 % faster.
- **Self-improving workflow.** A second "operations" team changed how the loop ran while it was
  running: deeper experiments in rounds (day 6), parallel rounds (day 10), and a cheap quick check
  that retires an idea before a long experiment (day 18; 28 of 37 retired experiments after it
  ended at that check or at a prototype).
- **What the wins looked like.** Stopping GROUP BY early under LIMIT without ORDER BY (460 ms to
  23 ms on one query), caching decoded string dictionaries across queries, filtering on dictionary
  codes, one dictionary per column, a shorter per-query server path.

*Taken:* the bar fixed before measurement, the "% or ms, whichever is larger" regression rule,
alternating run order, the shared record with written reasons, the adversarial review criteria.
*Not yet:* the operations team and the quick check (see the plan).

## VibeServe (Kamahori et al.)

Agents synthesise whole LLM serving systems per deployment. The architecture is what this project
copies most directly.

- **Inputs** are a small set of user artifacts: reference implementation, accuracy checker,
  benchmark script, hardware description. The checker is the source of truth.
- **Outer loop** plans over git checkpoints with structured, persistent state: an issue backlog,
  a long-term memory file, the commit history. It hands the inner loop one task with acceptance
  criteria. This lets it separate design failures from implementation flaws.
- **Inner loop** has an Implementer, an Accuracy Judge and a Performance Evaluator, each in a
  fresh context. The Judge runs the checker, checks the criteria, and inspects the code for reward
  hacking. Artifacts are mounted read-only.
- **Skills library** of domain knowledge organised by layer.
- **Ablations** (their Table 1): a single long-running agent reached 617 tok/s in 35 h against
  about 10k for the full pipeline, and skipped its own gates; without skills, 1,100 tok/s;
  replacing the issue tracker with evolutionary search, 537 tok/s.

*Taken:* outer/inner split, issue-tracker policy with a memory file, fresh context per role,
read-only checks owned by the harness, the knowledge directory.

## Bespoke OLAP (Wehrstein et al.)

Generates a new workload-specific engine from scratch (11x over DuckDB on TPC-H in their setup).
A different goal from ours, but the infrastructure lessons transfer.

- Agents are "systematically unreliable at recognizing when a change has made things worse", so
  an **external monitor** compares every change against the accepted baseline and rolls back.
- Correctness is tested across many parameter instantiations and on several scaled-down datasets
  "preventing hardcoding to exact row ids or counts".
- Fast iteration matters: hotpatching cut turnaround from minutes to seconds.
- Bounded subproblems: the pipeline's value is in structuring the task, not in a smarter model.

*Taken:* monotonic improvement enforced outside the agent, multiple bindings per template, a
second dataset. *Not applicable:* hotpatching (we rebuild a real engine; ccache and persistent
build directories are the substitute).

## JetStream (Balasingam et al.)

Generates per-template accelerators that live inside an existing DBMS.

- The orchestrator builds, runs gates and A/B benchmarks each attempt against the best validated
  version; it replaces it only if correct and faster.
- A **learned memory** of failed hypotheses, bottlenecks and useful profiles: with it, 211x at
  $1.76 per query; without, 15.2x at $6.00.
- Their single-agent baseline "hardcoded accelerators for the parameter bindings in the exposed
  tests and failed on the hidden full set", which the pipeline prevents "by having the
  orchestrator own the tests and the gates that run them".

*Taken:* hidden bindings owned by the harness; memory compressed between attempts.

## GenDB-V (Lao and Trummer)

Synthesises engines together with machine-checked proofs of SQL correctness.

- Performance-first exploration: prototype and measure without the verifier, then prove only the
  winning design.
- Engine synthesis proceeds across sequential versions; a candidate replaces the active version
  only if it passes verification and improves workload time.
- Their audit found wrong answers in a testing-based synthesis method for 16 of 28 templates, a
  reminder of how much differential testing on sampled inputs can miss.
- Uses SEC-EDGAR as a benchmark to reduce training-data leakage.

*Taken:* sequential versions with a replace-only-if-better rule; cheap measurement before
expensive validation. *Noted for later:* a leakage-free workload; stronger correctness evidence
than differential tests.

## Where db_evolve sits

Bespoke OLAP, GenDB-V and JetStream specialise *to a fixed set of templates* and are evaluated on
those templates. Intent Lab improves a general engine but optimises directly on the benchmark and
relies on review for generality. db_evolve improves a general engine and **measures**
generalisation: templates are split, and the reported number is on templates no agent saw.
