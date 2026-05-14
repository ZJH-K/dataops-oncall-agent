---
doc_type: table
skill_name: data_volume_drop
table_name: dws_sales_daily
---

# dws_sales_daily Table

## Purpose

`dws_sales_daily` is a DWS aggregate table for daily sales metrics. It is consumed by `ads_sales_report` and `ads_revenue_dashboard`.

## Freshness And Partition

The table is partitioned by `dt` and should be produced daily by `dws_sales_daily_job`. A missing partition or severe row count drop may affect business sales reporting.

## Important Quality Signals

- Daily row count should stay near the seven-day average.
- A drop larger than 50 percent should be treated as high risk.
- Payment order upstream data is important for complete revenue aggregation.

