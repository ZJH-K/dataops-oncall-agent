---
doc_type: runbook
skill_name: partition_missing
table_name: dws_sales_daily
---

# Partition Missing Runbook

## Symptom

Use this runbook when a table partition such as `dt=2026-05-14` is missing, delayed, failed, or not ready. Chinese alerts often say "没有生成分区", "未产出", or "分区缺失".

## Required Evidence

- Query the target table partition status for the business date.
- Query the producing task run status.
- Check upstream partitions if the producing task is upstream_failed.
- Query downstream lineage to estimate report impact.

## Diagnosis Notes

If `dws_sales_daily` partition `dt=2026-05-14` is missing and `dws_sales_daily_job` is upstream_failed, do not conclude the root cause from the partition alone. Confirm upstream task and upstream partition evidence first.

