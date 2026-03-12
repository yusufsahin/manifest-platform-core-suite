import pytest

from mpc.kernel.errors import (
    ERROR_CODES,
    REASON_CODES,
    INTENT_KINDS,
    validate_error_code,
    validate_reason_code,
    validate_intent_kind,
    validate_all_codes,
    MPCError,
    MPCBudgetError,
)


class TestErrorCodeRegistry:
    def test_all_error_codes_are_prefixed(self):
        for code in ERROR_CODES:
            assert code.startswith("E_"), f"{code} should start with E_"

    def test_all_reason_codes_are_prefixed(self):
        for code in REASON_CODES:
            assert code.startswith("R_"), f"{code} should start with R_"

    def test_validate_known_error_code(self):
        validate_error_code("E_PARSE_SYNTAX")

    def test_validate_unknown_error_code(self):
        with pytest.raises(ValueError, match="Unknown error code"):
            validate_error_code("E_NONEXISTENT")

    def test_validate_known_reason_code(self):
        validate_reason_code("R_POLICY_ALLOW")

    def test_validate_unknown_reason_code(self):
        with pytest.raises(ValueError, match="Unknown reason code"):
            validate_reason_code("R_NONEXISTENT")

    def test_validate_known_intent_kind(self):
        validate_intent_kind("maskField")

    def test_validate_unknown_intent_kind(self):
        with pytest.raises(ValueError, match="Unknown intent kind"):
            validate_intent_kind("unknownKind")

    def test_intent_kinds_complete(self):
        expected = {
            "maskField", "notify", "revoke", "grantRole", "audit",
            "transform", "tag", "rateLimit", "redirect", "publish", "rollback",
        }
        assert INTENT_KINDS == expected


class TestValidateAllCodes:
    def test_clean_output(self):
        output = {"allow": True, "reasons": [{"code": "R_POLICY_ALLOW"}]}
        assert validate_all_codes(output) == []

    def test_unknown_error_code(self):
        output = {"error": {"code": "E_FAKE_CODE", "message": "x", "severity": "error"}}
        violations = validate_all_codes(output)
        assert len(violations) == 1
        assert "E_FAKE_CODE" in violations[0]

    def test_unknown_reason_code(self):
        output = {"allow": False, "reasons": [{"code": "R_FAKE"}]}
        violations = validate_all_codes(output)
        assert len(violations) == 1

    def test_unknown_intent_kind(self):
        output = {
            "intents": [{"kind": "fakeKind", "target": "x"}]
        }
        violations = validate_all_codes(output)
        assert len(violations) == 1

    def test_valid_intent_kind(self):
        output = {
            "intents": [{"kind": "maskField", "target": "user.ssn"}]
        }
        assert validate_all_codes(output) == []


class TestExceptions:
    def test_mpc_error(self):
        exc = MPCError("E_PARSE_SYNTAX", "bad token")
        assert exc.code == "E_PARSE_SYNTAX"
        assert "bad token" in str(exc)

    def test_mpc_budget_error(self):
        exc = MPCBudgetError("E_BUDGET_EXCEEDED", "too many steps", limit=100)
        assert exc.limit == 100
        assert exc.code == "E_BUDGET_EXCEEDED"

    def test_mpc_validation_error_uses_registered_code(self):
        """BUG-8 regression: MPCValidationError.code must be in ERROR_CODES."""
        from mpc.kernel.errors import MPCValidationError
        exc = MPCValidationError([])
        assert exc.code in ERROR_CODES
