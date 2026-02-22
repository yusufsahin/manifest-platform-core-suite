# Notes

When all input decisions allow, deny-wins composition MUST produce allow=true.
All reasons from all allowing decisions are collected and included in the output,
sorted by code ascending (lexicographic) for deterministic ordering.
Final: allow=true, reasons=[R_ACL_ALLOW_ROLE, R_POLICY_ALLOW].
