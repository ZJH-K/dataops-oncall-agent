# Null Rate Spike

## Goal

Diagnose whether a field-level null rate spike is a data quality incident and estimate the affected downstream scope.

## Required Evidence

- Null rate trend for the target table and field.
- Quality check threshold and current check status.
- Related task status for upstream and producing jobs.
- Downstream lineage impact.

## Report Expectations

The report should include the observed null rate, threshold, affected field, and downstream impact. If field-level evidence is unavailable, the report must ask for clarification.
