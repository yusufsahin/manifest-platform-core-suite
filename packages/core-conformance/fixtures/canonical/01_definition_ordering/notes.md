# Notes

Definitions MUST be ordered deterministically: priority desc, then name asc, then id asc.

Input has three definitions in arbitrary order. After canonicalization:
- id=a (priority=2, name=alpha) sorts first — highest priority
- id=b (priority=1, name=beta) sorts before id=c (same priority, beta < gamma lexicographically)
- id=c (priority=1, name=gamma) sorts last

Object keys within each definition are also sorted lexicographically (id, name, priority).
