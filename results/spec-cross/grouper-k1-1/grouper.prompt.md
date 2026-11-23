You are the grouper in db_evolve's specialisation study. Several copies of a database engine
(duckdb) were each specialised by other agents for one query template. Each specialised system
is the original engine plus one diff. The next step merges the diffs into a fixed number of
systems, and every template will then run on the system of its group.

Split the 8 templates below into exactly **1 groups**. Each template goes in exactly one
group, and no group is empty. Each group's diffs will be merged into one engine by another agent.

## What makes a good grouping

- Put together diffs that are compatible: they change different code, or change the same code in
  the same direction, so one engine can keep all of them at full strength.
- Separate diffs that conflict: they change the same heuristic, threshold, plan rule or operator in
  opposite or incompatible ways, so one merged engine would have to give up some of the gain.
- Where you have to compromise, protect the largest gains (each template's own speedup is listed).
- Group sizes do not need to be equal.

## Material (in your working directory)

- `systems.md`: for each template, the speedup its own specialised system reached on it, the
  agents' summaries of what each accepted change does, and the files it touches.
- `patches/<template>.patch`: the full diff of each specialised system against the original
  engine. A template whose system made no change has no patch; put it in any group.

Read the patches, not only the summaries. You cannot run anything; reading is enough. Do not edit
files.

## Answer

Return `groups` (a list of 1 lists of template names) and `rationale` (a few sentences per
group: why these diffs fit together, and which conflicts you avoided by separating others).

Templates: q01, q02, q09, q13, q16, q18, q19, q21
