# MPC Scope

## In scope

- Manifest parsing (`mpc.kernel.parser`), validation (`mpc.tooling.validator`), canonicalization (`mpc.kernel.canonical`), and compilation (`mpc.tooling.registry`)
- Workflow (`mpc.features.workflow`), policy (`mpc.features.policy`), ACL (`mpc.features.acl`), expression engine (`mpc.features.expr`)
- Contracts (`mpc.kernel.contracts`: EventEnvelope, Decision, Error, Intent, Trace)
- Redaction of **configurable keys** (e.g. `denyKeys`): masking of fields in trace/error/output via `mpc.features.redaction`
- Conformance: contracts, canonical, workflow (`mpc.tooling.conformance`)
- GuardPort / AuthPort interfaces for consuming apps

## Out of scope

- **PII (personally identifiable information)** handling, compliance, or guarantees. MPC does not process, classify, or redact data for GDPR/privacy purposes. The redaction engine is for **configurable denyKeys** (e.g. API keys, internal fields); it is **not** a PII redaction or privacy tool.
- Security conformance fixtures that assert “no PII in trace” or “PII in error redacted” are **out of scope** and are not part of the normative conformance suite.

— ↑ [README](../README.md) | [BACKLOG](BACKLOG.md)
