# Notes

Overlay merge op performs a shallow merge of the value object into the target path.
Existing keys not present in the overlay value are preserved (effect, tags).
Keys present in both are overwritten by the overlay value (ttl: 3600 → 7200).
New keys from the overlay value are added (owner). Output keys sorted lexicographically.
