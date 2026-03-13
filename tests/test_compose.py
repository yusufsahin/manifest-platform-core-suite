"""Tests for decision composition engine (D6)."""
import pytest

from mpc.kernel.contracts.models import Decision, Intent, Reason
from mpc.features.compose.engine import compose_decisions, ComposeResult


class TestDenyWins:
    def test_single_allow(self):
        decisions = [Decision(allow=True, reasons=[Reason(code="R_POLICY_ALLOW")])]
        result = compose_decisions(decisions)
        assert result.allow is True
        assert len(result.reasons) == 1
        assert result.reasons[0].code == "R_POLICY_ALLOW"

    def test_single_deny(self):
        decisions = [Decision(allow=False, reasons=[Reason(code="R_ACL_DENY_ROLE")])]
        result = compose_decisions(decisions)
        assert result.allow is False

    def test_deny_overrides_allow(self):
        decisions = [
            Decision(allow=True, reasons=[Reason(code="R_POLICY_ALLOW")]),
            Decision(allow=False, reasons=[Reason(code="R_ACL_DENY_ROLE")]),
        ]
        result = compose_decisions(decisions)
        assert result.allow is False
        assert any(r.code == "R_ACL_DENY_ROLE" for r in result.reasons)

    def test_all_allow_collected(self):
        decisions = [
            Decision(allow=True, reasons=[Reason(code="R_ACL_ALLOW_ROLE")]),
            Decision(allow=True, reasons=[Reason(code="R_POLICY_ALLOW")]),
        ]
        result = compose_decisions(decisions)
        assert result.allow is True
        codes = [r.code for r in result.reasons]
        assert "R_ACL_ALLOW_ROLE" in codes
        assert "R_POLICY_ALLOW" in codes

    def test_deny_only_deny_reasons(self):
        decisions = [
            Decision(allow=True, reasons=[Reason(code="R_POLICY_ALLOW")]),
            Decision(allow=False, reasons=[Reason(code="R_ACL_DENY_ROLE")]),
        ]
        result = compose_decisions(decisions)
        assert result.allow is False
        codes = [r.code for r in result.reasons]
        assert "R_POLICY_ALLOW" not in codes
        assert "R_ACL_DENY_ROLE" in codes

    def test_empty_decisions(self):
        result = compose_decisions([])
        assert result.allow is True
        assert result.reasons == []


class TestIntentDedup:
    def test_duplicate_removed(self):
        decisions = [
            Decision(
                allow=True,
                intents=[Intent(kind="maskField", target="user.ssn")],
            ),
            Decision(
                allow=True,
                intents=[Intent(kind="maskField", target="user.ssn")],
            ),
        ]
        result = compose_decisions(decisions)
        assert len(result.intents) == 1
        assert result.intents[0].target == "user.ssn"

    def test_different_targets_kept(self):
        decisions = [
            Decision(
                allow=True,
                intents=[Intent(kind="maskField", target="user.ssn")],
            ),
            Decision(
                allow=True,
                intents=[Intent(kind="maskField", target="user.salary")],
            ),
        ]
        result = compose_decisions(decisions)
        assert len(result.intents) == 2

    def test_dedup_by_idempotency_key(self):
        decisions = [
            Decision(
                allow=True,
                intents=[Intent(kind="notify", target="admin", idempotency_key="k1")],
            ),
            Decision(
                allow=True,
                intents=[Intent(kind="notify", target="admin", idempotency_key="k1")],
            ),
            Decision(
                allow=True,
                intents=[Intent(kind="notify", target="admin", idempotency_key="k2")],
            ),
        ]
        result = compose_decisions(decisions)
        assert len(result.intents) == 2

    def test_preserves_order(self):
        decisions = [
            Decision(
                allow=True,
                intents=[
                    Intent(kind="audit", target="log"),
                    Intent(kind="notify", target="admin"),
                ],
            ),
            Decision(
                allow=True,
                intents=[
                    Intent(kind="audit", target="log"),
                    Intent(kind="tag", target="entity"),
                ],
            ),
        ]
        result = compose_decisions(decisions)
        kinds = [i.kind for i in result.intents]
        assert kinds == ["audit", "notify", "tag"]


class TestAllowWins:
    def test_allow_wins_strategy(self):
        decisions = [
            Decision(allow=True, reasons=[Reason(code="R_POLICY_ALLOW")]),
            Decision(allow=False, reasons=[Reason(code="R_ACL_DENY_ROLE")]),
        ]
        result = compose_decisions(decisions, strategy="allow-wins")
        assert result.allow is True

    def test_allow_wins_collects_all_reasons(self):
        decisions = [
            Decision(allow=True, reasons=[Reason(code="R_POLICY_ALLOW")]),
            Decision(allow=False, reasons=[Reason(code="R_ACL_DENY_ROLE")]),
        ]
        result = compose_decisions(decisions, strategy="allow-wins")
        codes = [r.code for r in result.reasons]
        assert "R_POLICY_ALLOW" in codes
        assert "R_ACL_DENY_ROLE" in codes

    def test_allow_wins_all_deny(self):
        decisions = [
            Decision(allow=False, reasons=[Reason(code="R_POLICY_DENY")]),
            Decision(allow=False, reasons=[Reason(code="R_ACL_DENY_ROLE")]),
        ]
        result = compose_decisions(decisions, strategy="allow-wins")
        assert result.allow is False

    def test_allow_wins_intents_deduped(self):
        decisions = [
            Decision(allow=True, intents=[Intent(kind="audit", target="log")]),
            Decision(allow=False, intents=[Intent(kind="audit", target="log")]),
        ]
        result = compose_decisions(decisions, strategy="allow-wins")
        assert len(result.intents) == 1

    def test_unknown_strategy_falls_back_to_deny_wins(self):
        decisions = [
            Decision(allow=True, reasons=[Reason(code="R_POLICY_ALLOW")]),
            Decision(allow=False, reasons=[Reason(code="R_ACL_DENY_ROLE")]),
        ]
        result = compose_decisions(decisions, strategy="unknown-strategy")
        assert result.allow is False
