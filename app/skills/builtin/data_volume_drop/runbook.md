# Data Volume Drop

## Goal

Diagnose whether a sudden table row count drop is a data incident and identify likely upstream causes.

## Required Evidence

- Recent row count trend for the target table.
- Current partition status for the business date.
- Related task run status for producing and upstream DAGs.
- Downstream lineage impact.

## Report Expectations

The report should cite row count trend evidence, quantify the drop, and avoid claiming a root cause if upstream task or partition evidence is missing.
