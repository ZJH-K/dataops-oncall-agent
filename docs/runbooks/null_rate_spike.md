---
doc_type: runbook
skill_name: null_rate_spike
table_name: ads_user_profile
---

# Null Rate Spike Runbook

## Symptom

Use this runbook when a field null rate suddenly rises, such as "ads_user_profile user_id 字段空值率突然升高" or "null rate spike". This is a field-level data quality incident pattern.

## Required Evidence

- Query null-rate trend with `query_null_rate`.
- Compare actual_value with threshold and expected_value.
- Query related task runs for upstream and producing jobs.
- Query lineage from the affected table to estimate downstream impact.

## Diagnosis Notes

For the demo incident, `ads_user_profile.user_id` reaches `0.35` null rate on `2026-05-14`, while the threshold is `0.02`. The likely cause is an abnormal user identity mapping rule, even if the producing task status is success.

