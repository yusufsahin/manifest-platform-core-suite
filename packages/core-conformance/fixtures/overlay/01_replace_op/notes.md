# Notes

Overlay replace op MUST overwrite the value at the specified path without affecting
sibling keys. Selector MUST match by (kind, namespace, id). Unmatched keys are preserved.

Input: base Policy with attributes.effect="allow". Overlay replaces attributes.effect with "deny".
Expected: same object with attributes.effect="deny", ttl=3600 preserved.
Output object keys are sorted lexicographically per canonical JSON rules.
