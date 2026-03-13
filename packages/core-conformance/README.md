# `mpc.tooling.conformance` (Normative)

This folder defines the **normative conformance fixtures**.

Each fixture directory contains:
- input.json (or input.dsl / input.yaml)
- expected.json (canonical)
- meta.json (fixed clock, preset, limits)
- notes.md (normative explanation)

A conformance runner MUST:
1) fix clock
2) run the target component (schema validate / parse / eval / merge / compose / activate)
3) canonicalize output
4) byte-compare with expected.json
5) report diffs + trace snippet

Fixtures are the constitution: implementations must match these outputs.
