# Airflow Task Failed

## Goal

Diagnose a failed scheduled data pipeline task and determine whether it affects downstream tables or reports.

## Required Evidence

- Task run status for the target DAG and business date.
- Error type, error message, retry count, and log excerpt.
- Produced table for the failed DAG.
- Downstream lineage from the produced table.

## Report Expectations

The report should cite the failed task evidence and downstream impact. If task run data is missing, the report must say the evidence is insufficient.
