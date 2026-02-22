import json

from mpc.canonical import canonicalize, canonicalize_bytes, stable_hash, order_definitions


class TestCanonicalize:
    def test_key_sorting(self):
        result = canonicalize({"zebra": True, "apple": 1})
        assert result == '{"apple":1,"zebra":true}'

    def test_nested_key_sorting(self):
        data = {"z": {"b": 2, "a": 1}, "a": 0}
        result = canonicalize(data)
        assert result == '{"a":0,"z":{"a":1,"b":2}}'

    def test_array_order_preserved(self):
        data = {"arr": [3, 1, 2]}
        result = canonicalize(data)
        assert result == '{"arr":[3,1,2]}'

    def test_no_whitespace(self):
        result = canonicalize({"a": [1, 2], "b": {"c": 3}})
        assert " " not in result
        assert "\n" not in result

    def test_idempotence(self):
        data = {"z": 1, "a": 2, "m": {"y": 3, "x": 4}}
        c1 = canonicalize(data)
        c2 = canonicalize(json.loads(c1))
        assert c1 == c2

    def test_empty_object(self):
        assert canonicalize({}) == "{}"

    def test_empty_array(self):
        assert canonicalize([]) == "[]"

    def test_unicode(self):
        data = {"emoji": "\U0001f600", "turkish": "\u00e7"}
        result = canonicalize(data)
        parsed = json.loads(result)
        assert parsed["emoji"] == "\U0001f600"
        assert parsed["turkish"] == "\u00e7"


class TestCanonicalizeBytes:
    def test_utf8(self):
        data = {"key": "value"}
        raw = canonicalize_bytes(data)
        assert isinstance(raw, bytes)
        assert raw == b'{"key":"value"}'


class TestStableHash:
    def test_same_data_different_key_order(self):
        h1 = stable_hash({"b": 2, "a": 1})
        h2 = stable_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_data(self):
        h1 = stable_hash({"a": 1})
        h2 = stable_hash({"a": 2})
        assert h1 != h2

    def test_hash_is_hex(self):
        h = stable_hash({"x": 1})
        assert len(h) == 64
        int(h, 16)  # must be valid hex


class TestOrderDefinitions:
    def test_priority_desc(self):
        defs = [
            {"id": "a", "priority": 1},
            {"id": "b", "priority": 3},
            {"id": "c", "priority": 2},
        ]
        result = order_definitions(defs)
        assert [d["id"] for d in result] == ["b", "c", "a"]

    def test_name_asc_when_same_priority(self):
        defs = [
            {"id": "x", "name": "beta", "priority": 1},
            {"id": "y", "name": "alpha", "priority": 1},
        ]
        result = order_definitions(defs)
        assert [d["id"] for d in result] == ["y", "x"]

    def test_id_asc_when_same_priority_and_name(self):
        defs = [
            {"id": "b", "name": "same", "priority": 1},
            {"id": "a", "name": "same", "priority": 1},
        ]
        result = order_definitions(defs)
        assert [d["id"] for d in result] == ["a", "b"]

    def test_full_ordering(self):
        defs = [
            {"id": "c", "name": "gamma", "priority": 1},
            {"id": "a", "name": "alpha", "priority": 2},
            {"id": "b", "name": "beta", "priority": 1},
        ]
        result = order_definitions(defs)
        assert [d["id"] for d in result] == ["a", "b", "c"]

    def test_missing_fields_default(self):
        defs = [{"id": "b"}, {"id": "a"}]
        result = order_definitions(defs)
        assert [d["id"] for d in result] == ["a", "b"]
