# Notes

Enterprise mode: artifact has a signature field but the signature does not verify
against the artifact payload. The engine MUST produce E_GOV_SIGNATURE_INVALID with
severity=fatal. A failed signature MUST halt activation — it is not recoverable
and MUST NOT fall through to a policy decision. Severity is fatal (not error) because
a bad signature indicates potential tampering.
