# Notes

RBAC ACL: actor has role 'viewer' which is not listed in any rule granting 'delete'.
No rule matches, so the request MUST be denied with R_ACL_DENY_ROLE.

With denyByDefaultACL=true (preset-security-hardened), any action not explicitly
granted MUST be denied. The viewer role has no rules at all, so delete is denied.
