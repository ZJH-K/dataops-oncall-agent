---
doc_type: postmortem
skill_name: null_rate_spike
table_name: ads_user_profile
---

# User Identity Null Spike 2026-05

## Summary

On `2026-05-14`, `ads_user_profile.user_id` null rate rose to `35%`. The producing task completed successfully, but the identity mapping rule emitted null identifiers.

## Impact

User profile dashboard coverage dropped and CRM segmentation became unreliable for the affected partition.

## Prevention

Add a hard null-rate gate for `user_id` and require manual confirmation before publishing ADS user profile data when null rate exceeds 2 percent.

