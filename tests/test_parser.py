"""Tests for all three parser frontends: JSON, YAML, DSL.

Core invariant: given semantically identical input in any format,
all frontends MUST produce the same ManifestAST.
"""
import pytest
import json
import textwrap

from mpc.parser import parse, parse_json, parse_yaml, parse_dsl
from mpc.errors import MPCError


# ---------------------------------------------------------------------------
# JSON frontend
# ---------------------------------------------------------------------------

class TestJsonFrontend:
    def test_minimal(self):
        raw = json.dumps({
            "schemaVersion": 1,
            "namespace": "acme",
            "name": "rules",
            "manifestVersion": "1.0.0",
            "defs": [],
        })
        ast = parse_json(raw)
        assert ast.namespace == "acme"
        assert ast.defs == []

    def test_with_defs(self):
        raw = json.dumps({
            "schemaVersion": 1,
            "namespace": "acme",
            "name": "rules",
            "manifestVersion": "1.0.0",
            "defs": [
                {"kind": "Policy", "id": "p1", "effect": "allow"},
            ],
        })
        ast = parse_json(raw)
        assert len(ast.defs) == 1
        assert ast.defs[0].kind == "Policy"
        assert ast.defs[0].properties["effect"] == "allow"

    def test_invalid_json(self):
        with pytest.raises(MPCError) as exc_info:
            parse_json("{invalid")
        assert exc_info.value.code == "E_PARSE_SYNTAX"

    def test_non_object_root(self):
        with pytest.raises(MPCError) as exc_info:
            parse_json("[1, 2, 3]")
        assert exc_info.value.code == "E_PARSE_SYNTAX"


# ---------------------------------------------------------------------------
# YAML frontend
# ---------------------------------------------------------------------------

class TestYamlFrontend:
    def test_minimal(self):
        yaml_text = textwrap.dedent("""\
            schemaVersion: 1
            namespace: acme
            name: rules
            manifestVersion: "1.0.0"
            defs: []
        """)
        ast = parse_yaml(yaml_text)
        assert ast.namespace == "acme"

    def test_with_defs(self):
        yaml_text = textwrap.dedent("""\
            schemaVersion: 1
            namespace: acme
            name: rules
            manifestVersion: "1.0.0"
            defs:
              - kind: Policy
                id: p1
                effect: allow
        """)
        ast = parse_yaml(yaml_text)
        assert len(ast.defs) == 1
        assert ast.defs[0].properties["effect"] == "allow"

    def test_invalid_yaml(self):
        with pytest.raises(MPCError) as exc_info:
            parse_yaml(":\n  :\n  - :")
        assert exc_info.value.code == "E_PARSE_SYNTAX"


# ---------------------------------------------------------------------------
# DSL frontend (Lark)
# ---------------------------------------------------------------------------

class TestDslFrontend:
    def test_minimal(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "acme"
            @name "rules"
            @version "1.0.0"
        """)
        ast = parse_dsl(dsl)
        assert ast.schema_version == 1
        assert ast.namespace == "acme"
        assert ast.name == "rules"
        assert ast.manifest_version == "1.0.0"

    def test_definition(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "acme"
            @name "rules"
            @version "1.0.0"

            def Policy allow_editors "AllowEditors" {
                effect: "allow"
                priority: 10
            }
        """)
        ast = parse_dsl(dsl)
        assert len(ast.defs) == 1
        node = ast.defs[0]
        assert node.kind == "Policy"
        assert node.id == "allow_editors"
        assert node.name == "AllowEditors"
        assert node.properties["effect"] == "allow"
        assert node.properties["priority"] == 10

    def test_multiple_definitions(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "acme"
            @name "rules"
            @version "1.0.0"

            def Policy p1 {
                effect: "allow"
            }

            def Policy p2 {
                effect: "deny"
            }
        """)
        ast = parse_dsl(dsl)
        assert len(ast.defs) == 2

    def test_nested_object(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "ns"
            @name "n"
            @version "1.0.0"

            def Policy p1 {
                match: { kind: "delete", target: "entity" }
            }
        """)
        ast = parse_dsl(dsl)
        match = ast.defs[0].properties["match"]
        assert isinstance(match, dict)
        assert match["kind"] == "delete"

    def test_array_value(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "ns"
            @name "n"
            @version "1.0.0"

            def Workflow wf1 {
                states: ["draft", "published"]
            }
        """)
        ast = parse_dsl(dsl)
        states = ast.defs[0].properties["states"]
        assert states == ["draft", "published"]

    def test_boolean_and_null(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "ns"
            @name "n"
            @version "1.0.0"

            def Config c1 {
                enabled: true
                disabled: false
                empty: null
            }
        """)
        ast = parse_dsl(dsl)
        p = ast.defs[0].properties
        assert p["enabled"] is True
        assert p["disabled"] is False
        assert p["empty"] is None

    def test_line_comments(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "ns"
            @name "n"
            @version "1.0.0"
            // this is a comment
            def Policy p1 {
                effect: "allow" // inline comment
            }
        """)
        ast = parse_dsl(dsl)
        assert len(ast.defs) == 1

    def test_source_map(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "ns"
            @name "n"
            @version "1.0.0"

            def Policy p1 {
                effect: "allow"
            }
        """)
        ast = parse_dsl(dsl)
        assert ast.defs[0].source is not None
        assert ast.defs[0].source.line is not None

    def test_parse_error(self):
        with pytest.raises(MPCError) as exc_info:
            parse_dsl("def ??? {{{")
        assert exc_info.value.code == "E_PARSE_SYNTAX"


# ---------------------------------------------------------------------------
# Auto-detect format
# ---------------------------------------------------------------------------

class TestAutoDetect:
    def test_detects_json(self):
        raw = json.dumps({"schemaVersion": 1, "namespace": "a", "name": "b", "manifestVersion": "1.0.0", "defs": []})
        ast = parse(raw)
        assert ast.namespace == "a"

    def test_detects_yaml(self):
        yaml_text = "schemaVersion: 1\nnamespace: a\nname: b\nmanifestVersion: '1.0.0'\ndefs: []\n"
        ast = parse(yaml_text)
        assert ast.namespace == "a"

    def test_detects_dsl(self):
        dsl = '@schema 1\n@namespace "a"\n@name "b"\n@version "1.0.0"\n'
        ast = parse(dsl)
        assert ast.namespace == "a"

    def test_explicit_format(self):
        raw = json.dumps({"schemaVersion": 1, "namespace": "x", "name": "y", "manifestVersion": "1.0.0", "defs": []})
        ast = parse(raw, format="json")
        assert ast.namespace == "x"


# ---------------------------------------------------------------------------
# Cross-format equivalence
# ---------------------------------------------------------------------------

class TestCrossFormatEquivalence:
    def test_json_yaml_produce_same_ast(self):
        json_text = json.dumps({
            "schemaVersion": 1,
            "namespace": "acme",
            "name": "rules",
            "manifestVersion": "1.0.0",
            "defs": [{"kind": "Policy", "id": "p1", "effect": "allow"}],
        })
        yaml_text = textwrap.dedent("""\
            schemaVersion: 1
            namespace: acme
            name: rules
            manifestVersion: "1.0.0"
            defs:
              - kind: Policy
                id: p1
                effect: allow
        """)
        ast_j = parse_json(json_text)
        ast_y = parse_yaml(yaml_text)

        assert ast_j.schema_version == ast_y.schema_version
        assert ast_j.namespace == ast_y.namespace
        assert len(ast_j.defs) == len(ast_y.defs)
        assert ast_j.defs[0].kind == ast_y.defs[0].kind
        assert ast_j.defs[0].properties == ast_y.defs[0].properties

    def test_dsl_produces_equivalent_ast(self):
        dsl_text = textwrap.dedent("""\
            @schema 1
            @namespace "acme"
            @name "rules"
            @version "1.0.0"

            def Policy p1 {
                effect: "allow"
            }
        """)
        json_text = json.dumps({
            "schemaVersion": 1,
            "namespace": "acme",
            "name": "rules",
            "manifestVersion": "1.0.0",
            "defs": [{"kind": "Policy", "id": "p1", "effect": "allow"}],
        })

        ast_d = parse_dsl(dsl_text)
        ast_j = parse_json(json_text)

        assert ast_d.schema_version == ast_j.schema_version
        assert ast_d.namespace == ast_j.namespace
        assert ast_d.name == ast_j.name
        assert ast_d.manifest_version == ast_j.manifest_version
        assert len(ast_d.defs) == len(ast_j.defs)
        assert ast_d.defs[0].kind == ast_j.defs[0].kind
        assert ast_d.defs[0].id == ast_j.defs[0].id
        assert ast_d.defs[0].properties == ast_j.defs[0].properties
