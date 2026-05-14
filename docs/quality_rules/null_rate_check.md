---
doc_type: quality_rule
skill_name: null_rate_spike
table_name: ads_user_profile
---

# Null Rate Check

## Rule

For identity fields such as `ads_user_profile.user_id`, compare actual null rate with expected value and threshold.

## Threshold

The demo threshold is `0.02`. A current null rate of `0.35` is a severe null_rate_spike and should be treated as P1 quality risk.

## Evidence Needed

Pair the null-rate check with related task runs and lineage. A successful task does not prove the data is correct if field-level quality checks fail.

