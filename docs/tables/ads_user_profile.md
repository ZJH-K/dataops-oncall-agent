---
doc_type: table
skill_name: null_rate_spike
table_name: ads_user_profile
---

# ads_user_profile Table

## Purpose

`ads_user_profile` is an ADS table for user profile and CRM scenarios. The table depends on `dwd_user_identity`.

## Critical Fields

- `user_id`: stable user identifier. A high null rate breaks downstream profile coverage and dashboard metrics.
- `dt`: business date partition.

## Important Quality Signals

`user_id` null rate should remain close to 0.5 percent and below the 2 percent threshold. A spike to 35 percent indicates a serious identity mapping or field derivation issue.

