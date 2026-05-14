---
doc_type: postmortem
skill_name: data_volume_drop
table_name: dws_sales_daily
---

# Payment Sync Failed 2026-05

## Summary

On `2026-05-14`, payment order source export was missing. `payment_orders_sync_daily` failed, `dwd_payment_order` was not produced, and `dws_sales_daily` row count dropped from `10000` to `800`.

## Impact

Sales reporting based on `ads_sales_report` and `ads_revenue_dashboard` was incomplete. Revenue metrics undercounted payment-related order rows.

## Prevention

Add upstream source-file freshness checks before `dws_sales_daily_job`, and block ADS publication when payment partitions are missing.

