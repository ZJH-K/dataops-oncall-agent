---
doc_type: runbook
skill_name: data_volume_drop
table_name: dws_sales_daily
---

# Data Volume Drop Runbook

## Symptom

Use this runbook when a table row count drops sharply, for example "dws_sales_daily 今日数据量较昨日下降 92%" or "row count drop". The `data_volume_drop` Diagnosis Skill should collect trend, partition, task, and lineage evidence before reporting a root cause.

## Required Evidence

- Query recent row count trend with `query_data_volume`.
- Confirm current partition status with `query_table_partitions`.
- Query related task runs, including upstream jobs.
- Query downstream lineage to identify affected reports and dashboards.

## Diagnosis Notes

For the demo incident, `dws_sales_daily` drops from `10000` rows to `800` rows on `2026-05-14`, with `change_ratio = -0.92`. The likely upstream evidence is `payment_orders_sync_daily` failed and payment order data is missing. The downstream impact includes `ads_sales_report` and `ads_revenue_dashboard`.

## Reporting Guidance

The final report must cite the row count trend and at least one tool result. If upstream evidence is unavailable, state that the data volume drop is confirmed but root cause evidence is insufficient.

