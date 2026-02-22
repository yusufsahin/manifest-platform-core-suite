# Notes

Canonical JSON requires all object keys sorted lexicographically (Unicode codepoint
order) at every level of nesting. Top-level keys: apple < banana < mango < zebra.
Nested object (mango): ant < zoo. Arrays preserve their original order — [3,1,2]
is NOT sorted; array ordering is controlled only by explicit ordering rules (e.g.
definition ordering), never by value sorting.
