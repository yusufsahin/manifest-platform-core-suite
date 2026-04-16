"""Error code, reason code, and intent kind registries.

All codes produced by MPC engines MUST be registered here.
The conformance runner rejects unknown codes.
"""
from __future__ import annotations

ERROR_CODES: frozenset[str] = frozenset({
    # Parse
    "E_PARSE_SYNTAX",
    "E_PARSE_INVALID_TOKEN",
    "E_PARSE_UNSUPPORTED_FORMAT",
    "E_PARSE_MISSING_REQUIRED",
    # Meta
    "E_META_UNKNOWN_KIND",
    "E_META_MISSING_REQUIRED_FIELD",
    "E_META_TYPE_NOT_ALLOWED",
    "E_META_FUNCTION_NOT_ALLOWED",
    "E_META_BREAKING_CHANGE",
    # Validation
    "E_VALID",
    "E_VALID_DUPLICATE_DEF",
    "E_VALID_UNRESOLVED_REF",
    "E_VALID_CYCLE_DETECTED",
    "E_VALID_NAMESPACE_CONFLICT",
    "E_VALID_INVALID_WORKFLOW",
    # Expr
    "E_EXPR_TYPE_MISMATCH",
    "E_EXPR_UNKNOWN_FUNCTION",
    "E_EXPR_LIMIT_DEPTH",
    "E_EXPR_LIMIT_STEPS",
    "E_EXPR_LIMIT_TIME",
    "E_EXPR_REGEX_LIMIT",
    "E_EXPR_DIV_BY_ZERO",
    "E_EXPR_INVALID_REGEX",
    "E_BUDGET_EXCEEDED",
    # Workflow
    "E_WF_NO_INITIAL",
    "E_WF_UNKNOWN_STATE",
    "E_WF_UNKNOWN_TRANSITION",
    "E_WF_GUARD_FAIL",
    "E_WF_AUTH_DENIED",
    # Policy
    "E_POLICY_INVALID_MATCHER",
    "E_POLICY_INVALID_TEMPLATE",
    # ACL
    "E_ACL_INVALID_RULE",
    "E_ACL_UNKNOWN_ACTION",
    # Overlay
    "E_OVERLAY_CONFLICT",
    "E_OVERLAY_UNKNOWN_SELECTOR",
    "E_OVERLAY_INVALID_OP",
    # Compose
    "E_COMPOSE_CONFLICT",
    # Form (Studio/Runtime)
    "E_FORM_DSL_TOO_LARGE",
    "E_FORM_DATA_TOO_LARGE",
    "E_FORM_ACTOR_TOO_LARGE",
    "E_FORM_EXPR_FAILED",
    "E_FORM_TIMEOUT",
    # Governance / Enterprise
    "E_GOV_SIGNATURE_REQUIRED",
    "E_GOV_SIGNATURE_INVALID",
    "E_GOV_ATTESTATION_MISSING",
    "E_GOV_ACTIVATION_FAILED",
    "E_QUOTA_EXCEEDED",
    # Runtime (Remote API)
    "E_RUNTIME_NOT_FOUND",
    "E_RUNTIME_FORBIDDEN",
    "E_RUNTIME_ACTIVE_REQUIRED",
    "E_RUNTIME_INTERNAL",
    "E_RUNTIME_DEPRECATED",
})

REASON_CODES: frozenset[str] = frozenset({
    # Policy
    "R_POLICY_ALLOW",
    "R_POLICY_DENY",
    # ACL
    "R_ACL_ALLOW_ROLE",
    "R_ACL_DENY_ROLE",
    "R_ACL_ALLOW_ABAC",
    "R_ACL_DENY_ABAC",
    # Workflow
    "R_WF_GUARD_PASS",
    "R_WF_GUARD_FAIL",
    "R_WF_AUTH_DENIED",
    "R_WF_QUEUED",
    "R_WF_IGNORED",
    # Governance
    "R_GOV_SIGNATURE_VALID",
    "R_GOV_ATTESTATION_PASSED",
})

INTENT_KINDS: frozenset[str] = frozenset({
    "maskField",
    "notify",
    "revoke",
    "grantRole",
    "audit",
    "transform",
    "tag",
    "rateLimit",
    "redirect",
    "publish",
    "rollback",
})


def validate_error_code(code: str) -> None:
    """Raise ValueError if *code* is not a registered E_* error code."""
    if code not in ERROR_CODES:
        raise ValueError(
            f"Unknown error code: '{code}'. "
            "Must be registered in ERROR_CODE_REGISTRY."
        )


def validate_reason_code(code: str) -> None:
    """Raise ValueError if *code* is not a registered R_* reason code."""
    if code not in REASON_CODES:
        raise ValueError(
            f"Unknown reason code: '{code}'. "
            "Must be registered in ERROR_CODE_REGISTRY."
        )


def validate_intent_kind(kind: str) -> None:
    """Raise ValueError if *kind* is not a registered intent kind."""
    if kind not in INTENT_KINDS:
        raise ValueError(
            f"Unknown intent kind: '{kind}'. "
            "Must be registered in INTENT_TAXONOMY."
        )


def validate_all_codes(output: object) -> list[str]:
    """Walk *output* and return a list of code/kind violations."""
    violations: list[str] = []
    _walk(output, violations)
    return violations


def _walk(obj: object, violations: list[str]) -> None:
    if isinstance(obj, dict):
        code = obj.get("code")
        if isinstance(code, str):
            if code.startswith("E_") and code not in ERROR_CODES:
                violations.append(f"Unknown error code: '{code}'")
            elif code.startswith("R_") and code not in REASON_CODES:
                violations.append(f"Unknown reason code: '{code}'")

        kind = obj.get("kind")
        if isinstance(kind, str):
            _is_intent = "target" in obj or "params" in obj or "idempotencyKey" in obj
            if _is_intent and kind not in INTENT_KINDS:
                violations.append(f"Unknown intent kind: '{kind}'")

        for value in obj.values():
            _walk(value, violations)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, violations)
