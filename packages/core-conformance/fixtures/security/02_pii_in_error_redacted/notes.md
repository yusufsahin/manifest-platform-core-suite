# Notes

Redaction MUST apply to Error.details, not only to Trace events. Any key listed
in redactionPolicy.denyKeys MUST be masked in all output surfaces including
errors returned to callers. The code, message, and severity fields are never
redacted — only user-supplied data fields (details, data) are candidates.
Expected output keys are sorted lexicographically per canonical JSON rules.
