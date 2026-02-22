"""Tests for redaction engine (Epic G1) — denyKeys masking."""
import pytest

from mpc.redaction import RedactionEngine, RedactionConfig


class TestRedactionEngine:
    def test_redacts_default_keys(self):
        engine = RedactionEngine()
        data = {"username": "alice", "password": "secret123", "token": "abc"}
        result = engine.redact(data)
        assert result["username"] == "alice"
        assert result["password"] == "***"
        assert result["token"] == "***"

    def test_original_not_modified(self):
        engine = RedactionEngine()
        data = {"password": "secret123"}
        result = engine.redact(data)
        assert data["password"] == "secret123"
        assert result["password"] == "***"

    def test_nested_redaction(self):
        engine = RedactionEngine()
        data = {"user": {"name": "alice", "password": "s", "auth": {"token": "t"}}}
        result = engine.redact(data)
        assert result["user"]["name"] == "alice"
        assert result["user"]["password"] == "***"
        assert result["user"]["auth"]["token"] == "***"

    def test_list_handling(self):
        engine = RedactionEngine()
        data = {"items": [{"name": "a", "secret": "x"}, {"name": "b", "secret": "y"}]}
        result = engine.redact(data)
        assert result["items"][0]["name"] == "a"
        assert result["items"][0]["secret"] == "***"
        assert result["items"][1]["secret"] == "***"

    def test_custom_deny_keys(self):
        config = RedactionConfig(deny_keys=frozenset({"email", "phone"}))
        engine = RedactionEngine(config=config)
        data = {"name": "alice", "email": "a@b.c", "phone": "555"}
        result = engine.redact(data)
        assert result["name"] == "alice"
        assert result["email"] == "***"
        assert result["phone"] == "***"

    def test_custom_mask_value(self):
        config = RedactionConfig(mask_value="[REDACTED]")
        engine = RedactionEngine(config=config)
        data = {"password": "s"}
        result = engine.redact(data)
        assert result["password"] == "[REDACTED]"

    def test_pattern_matching(self):
        config = RedactionConfig(
            deny_keys=frozenset(),
            deny_patterns=["internal_*", "debug.*"],
        )
        engine = RedactionEngine(config=config)
        data = {"debug": {"trace": "info"}, "public": "ok", "internal_id": "x"}
        result = engine.redact(data)
        assert result["public"] == "ok"
        assert result["internal_id"] == "***"

    def test_case_insensitive_keys(self):
        engine = RedactionEngine()
        data = {"Password": "secret", "TOKEN": "abc"}
        result = engine.redact(data)
        assert result["Password"] == "***"
        assert result["TOKEN"] == "***"

    def test_null_values_not_redacted_by_default(self):
        engine = RedactionEngine()
        data = {"password": None}
        result = engine.redact(data)
        assert result["password"] is None

    def test_null_values_redacted_when_configured(self):
        config = RedactionConfig(redact_null_values=True)
        engine = RedactionEngine(config=config)
        data = {"password": None}
        result = engine.redact(data)
        assert result["password"] == "***"

    def test_in_place_redaction(self):
        engine = RedactionEngine()
        data = {"password": "secret123"}
        engine.redact_in_place(data)
        assert data["password"] == "***"

    def test_empty_data(self):
        engine = RedactionEngine()
        assert engine.redact({}) == {}
        assert engine.redact([]) == []
        assert engine.redact("string") == "string"

    def test_ssn_redacted(self):
        engine = RedactionEngine()
        data = {"user": {"name": "Alice", "ssn": "123-45-6789"}}
        result = engine.redact(data)
        assert result["user"]["ssn"] == "***"

    def test_api_key_variants(self):
        engine = RedactionEngine()
        data = {"apiKey": "k1", "api_key": "k2", "authorization": "bearer xyz"}
        result = engine.redact(data)
        assert result["apiKey"] == "***"
        assert result["api_key"] == "***"
        assert result["authorization"] == "***"
