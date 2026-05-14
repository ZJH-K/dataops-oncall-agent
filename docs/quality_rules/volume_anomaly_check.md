---
doc_type: quality_rule
skill_name: data_volume_drop
table_name: dws_sales_daily
---

# Volume Anomaly Check

## Rule

For daily aggregate tables such as `dws_sales_daily`, compare current row_count with previous_day_row_count and seven_day_avg_row_count.

## Threshold

If `change_ratio <= -0.5`, classify the change as a data volume drop anomaly. If the affected table feeds ADS reporting, raise the risk level.

## Evidence Needed

The rule is not enough by itself. Pair the anomaly with partition status, related task runs, and lineage impact before producing a report.

