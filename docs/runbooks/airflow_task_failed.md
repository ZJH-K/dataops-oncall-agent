---
doc_type: runbook
skill_name: airflow_task_failed
table_name: dwd_order_detail
---

# Airflow Task Failed Runbook

## Symptom

Use this runbook when a scheduled DAG or task reports failed, upstream_failed, or retry exhaustion. Typical alerts include "DAG dwd_order_detail_daily failed" or "任务运行失败".

## Required Evidence

- Query task run status for the DAG and business date.
- Capture error_type, error_message, retry_count, and log_excerpt.
- Identify the produced table from DAG metadata.
- Query downstream lineage from the produced table.

## Diagnosis Notes

For `dwd_order_detail_daily` on `2026-05-14`, a SQL compile error for `payment_status` indicates a schema or SQL mapping problem. Treat downstream `dws_sales_daily` and `ads_sales_report` as at risk until the task succeeds or a backfill finishes.

