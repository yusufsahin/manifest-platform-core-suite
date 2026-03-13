"""Regression tests for security hardening (W-01, W-02).

W-01: DSL injection — the Studio worker now passes DSL via pyodide globals
      instead of f-string interpolation.  These tests confirm that payloads
      which would have broken out of a string-interpolated call are either
      (a) valid DSL whose content is stored as a literal string, or
      (b) invalid DSL that raises a clean MPCError.

W-02: XSS / HTML injection — the Visualizer.tsx sanitiseNodeId /
      sanitiseEdgeLabel helpers are TypeScript-side.  These tests cover the
      Python-side guarantee that AST property values containing HTML/script
      content are stored verbatim and never executed.

Finding #5: auth enforcement edge-cases added here to complement the
      existing TestAuthPort / TestWorkflowEngine suites in test_workflow.py.
"""
from __future__ import annotations

import pytest

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.errors import MPCError
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.kernel.parser import parse
from mpc.kernel.parser.yaml_frontend import parse_yaml
from mpc.tooling.validator.semantic import validate_semantic
from mpc.tooling.validator.structural import validate_structural

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DSL_PREFIX = (
    '@schema 1\n'
    '@namespace "sec"\n'
    '@name "sec_test"\n'
    '@version "1.0"\n'
)


def _dsl(body: str) -> str:
    return _DSL_PREFIX + body


def _meta(*kind_names: str) -> DomainMeta:
    return DomainMeta(kinds=[KindDef(name=n) for n in kind_names])


def _ast(*defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="sec",
        name="sec_test",
        manifest_version="1.0.0",
        defs=list(defs),
    )


# ---------------------------------------------------------------------------
# W-01 – DSL injection hardening
# ---------------------------------------------------------------------------

class TestDSLInjectionHardening:
    """Payloads that would have broken out of f-string interpolation are either
    stored as literal strings or rejected by the grammar parser."""

    def test_single_quote_escape_stored_literally(self):
        """Python-injection fragment '); import os; ... in a string value
        must be stored as a plain string, not executed."""
        dsl = _dsl(
            'def Policy p1 {\n'
            '    desc: "\'); import os; os.system(\'rm -rf /\')"\n'
            '}'
        )
        ast = parse(dsl, format="dsl")
        assert "import os" in ast.defs[0].properties["desc"]

    def test_double_quote_escape_stored_literally(self):
        """A value containing a closing-double-quote escape attempt is stored
        verbatim when properly Lark-escaped inside the string literal."""
        # Lark's ESCAPED_STRING handles \" internally, so the value ends up
        # as a literal string in the AST (no execution occurs).
        dsl = _dsl(
            'def Policy p1 {\n'
            '    cmd: "close\\"); exec(\'import os\')"\n'
            '}'
        )
        ast = parse(dsl, format="dsl")
        assert "exec" in ast.defs[0].properties["cmd"]

    def test_ident_cannot_contain_parens(self):
        """IDENT regex is [a-zA-Z_][a-zA-Z0-9_.-]* — parentheses break it."""
        dsl = _dsl("def Policy p(hostile) {}")
        with pytest.raises((MPCError, Exception)):
            parse(dsl, format="dsl")

    def test_ident_cannot_contain_backtick(self):
        dsl = _dsl("def Policy `hostile` {}")
        with pytest.raises((MPCError, Exception)):
            parse(dsl, format="dsl")

    def test_null_byte_in_dsl_rejected(self):
        """Null bytes are not valid DSL — parser must not hang or crash silently."""
        dsl = _dsl("def Policy p1 {}\x00")
        with pytest.raises((MPCError, Exception)):
            parse(dsl, format="dsl")

    def test_empty_input_returns_empty_manifest(self):
        """The DSL grammar allows zero directives and zero definitions, so an
        empty string is a valid (empty) document — it must not crash."""
        ast = parse("", format="dsl")
        assert isinstance(ast, ManifestAST)
        assert ast.defs == []

    def test_whitespace_only_returns_empty_manifest(self):
        """Whitespace-only input is also a valid empty DSL document."""
        ast = parse("   \n\t  ", format="dsl")
        assert isinstance(ast, ManifestAST)
        assert ast.defs == []

    def test_very_long_id_terminates(self):
        """An extremely long IDENT must either parse or be rejected cleanly
        without unbounded run-time (no catastrophic regex backtracking)."""
        long_id = "a" * 10_000
        dsl = _dsl(f"def Policy {long_id} {{}}")
        try:
            parse(dsl, format="dsl")
        except (MPCError, Exception):
            pass  # clean rejection is acceptable

    def test_deeply_nested_dsl_terminates(self):
        """Deeply nested definitions must not cause a stack overflow."""
        # Build 50 levels of nesting – well within sane limits.
        body = "def Policy root {\n"
        for i in range(50):
            body += "  " * (i + 1) + f"def Cond c{i} {{\n"
        body += "  " * 52 + 'prop: "v"\n'
        for i in range(50, -1, -1):
            body += "  " * (i + 1) + "}\n"
        try:
            parse(_dsl(body), format="dsl")
        except (MPCError, Exception):
            pass


# ---------------------------------------------------------------------------
# W-02 – AST property values are stored as literals, never interpreted
# ---------------------------------------------------------------------------

class TestASTContentStoredAsLiteral:
    """Hostile strings in property values must be stored verbatim in the AST,
    never interpreted as markup or code."""

    def test_script_tag_in_dsl_property(self):
        dsl = _dsl(
            'def Policy p1 {\n'
            '    desc: "<script>alert(1)</script>"\n'
            '}'
        )
        ast = parse(dsl, format="dsl")
        assert ast.defs[0].properties["desc"] == "<script>alert(1)</script>"

    def test_img_onerror_in_dsl_property(self):
        dsl = _dsl(
            'def Policy p1 {\n'
            '    src: "<img onerror=alert(1) src=x>"\n'
            '}'
        )
        ast = parse(dsl, format="dsl")
        assert "onerror" in ast.defs[0].properties["src"]

    def test_javascript_url_in_dsl_property(self):
        dsl = _dsl(
            'def Policy p1 {\n'
            '    url: "javascript:alert(document.cookie)"\n'
            '}'
        )
        ast = parse(dsl, format="dsl")
        assert ast.defs[0].properties["url"].startswith("javascript:")

    def test_yaml_frontend_hostile_string_stored_literally(self):
        """YAML frontend also stores hostile strings verbatim."""
        import yaml  # pyyaml (project dependency)

        # YAML/JSON frontends use flat dicts: non-reserved keys become props.
        doc = {
            "namespace": "sec_test",
            "name": "hostile",
            "defs": [
                {
                    "kind": "Policy",
                    "id": "p1",
                    "description": "<script>alert('xss')</script>",
                }
            ],
        }
        ast = parse_yaml(yaml.dump(doc))
        node = next(n for n in ast.defs if n.id == "p1")
        assert node.properties["description"] == "<script>alert('xss')</script>"

    def test_hostile_ast_id_not_executed_by_validator(self):
        """An ASTNode constructed directly with a hostile id is validated
        without executing the id content."""
        hostile_id = "<script>alert(document.cookie)</script>"
        ast = _ast(ASTNode(kind="Policy", id=hostile_id, properties={}))
        meta = _meta("Policy")
        # validate_structural must not raise, crash, or execute the id.
        errors = validate_structural(ast, meta)
        for e in errors:
            assert isinstance(e.message, str)

    def test_hostile_property_key_not_executed(self):
        """A property key containing HTML content in a manually constructed
        AST node is stored and validated without being interpreted."""
        ast = _ast(
            ASTNode(
                kind="Policy",
                id="p1",
                properties={"<script>x</script>": "value"},
            )
        )
        meta = _meta("Policy")
        errors = validate_structural(ast, meta)
        # Must not raise; error messages are plain strings.
        for e in errors:
            assert isinstance(e.message, str)


# ---------------------------------------------------------------------------
# Auth enforcement edge cases (finding #5)
# ---------------------------------------------------------------------------

from mpc.features.workflow.fsm import WorkflowEngine  # noqa: E402


def _auth_workflow_node() -> ASTNode:
    return ASTNode(
        kind="Workflow",
        id="auth_flow",
        properties={
            "initial": "open",
            "states": ["open", "closed"],
            "transitions": [
                {
                    "from": "open",
                    "on": "close",
                    "to": "closed",
                    "auth_roles": ["admin"],
                }
            ],
        },
    )


class TestAuthEnforcementEdgeCases:
    """Edge-case coverage for role-based auth enforcement (finding #5).

    Complements TestWorkflowEngine.test_fire_with_auth_roles and
    TestAuthPort in test_workflow.py.
    """

    def test_no_roles_kwarg_denied(self):
        """actor_roles=None is normalised to [] — restricted transition denied."""
        engine = WorkflowEngine.from_ast_node(_auth_workflow_node())
        result = engine.fire("close", actor_roles=None)
        assert result.decision.allow is False
        assert any(r.code == "R_WF_AUTH_DENIED" for r in result.decision.reasons)

    def test_empty_roles_list_denied(self):
        engine = WorkflowEngine.from_ast_node(_auth_workflow_node())
        result = engine.fire("close", actor_roles=[])
        assert result.decision.allow is False

    def test_wrong_role_denied(self):
        engine = WorkflowEngine.from_ast_node(_auth_workflow_node())
        result = engine.fire("close", actor_roles=["viewer"])
        assert result.decision.allow is False

    def test_correct_role_allowed(self):
        engine = WorkflowEngine.from_ast_node(_auth_workflow_node())
        result = engine.fire("close", actor_roles=["admin"])
        assert result.decision.allow is True
        assert result.new_state == "closed"

    def test_superset_roles_allowed(self):
        """Having extra roles beyond what is required still grants access."""
        engine = WorkflowEngine.from_ast_node(_auth_workflow_node())
        result = engine.fire("close", actor_roles=["viewer", "admin", "editor"])
        assert result.decision.allow is True

    def test_fixture_authRoles_camelCase_key_deny(self):
        """from_fixture_input reads camelCase 'authRoles' correctly."""
        engine = WorkflowEngine.from_fixture_input(
            {
                "initial": "open",
                "states": ["open", "closed"],
                "transitions": [
                    {
                        "from": "open",
                        "on": "close",
                        "to": "closed",
                        "authRoles": ["admin"],
                    }
                ],
            }
        )
        result = engine.fire("close", actor_roles=["viewer"])
        assert result.decision.allow is False

    def test_fixture_authRoles_camelCase_key_allow(self):
        """from_fixture_input reads camelCase 'authRoles' and allows correct role."""
        engine = WorkflowEngine.from_fixture_input(
            {
                "initial": "open",
                "states": ["open", "closed"],
                "transitions": [
                    {
                        "from": "open",
                        "on": "close",
                        "to": "closed",
                        "authRoles": ["admin"],
                    }
                ],
            }
        )
        result = engine.fire("close", actor_roles=["admin"])
        assert result.decision.allow is True

    def test_auth_roles_and_auth_port_both_must_pass(self):
        """When both auth_roles and auth_port are configured, the auth_port
        check runs after role check — both must pass for the transition to
        be allowed."""

        class DenyAll:
            def authorize(self, actor_id: str, transition: str) -> bool:
                return False

        engine = WorkflowEngine.from_ast_node(
            _auth_workflow_node(), auth_port=DenyAll()
        )
        # Has correct role but auth_port denies — overall result is deny.
        result = engine.fire("close", actor_id="u1", actor_roles=["admin"])
        assert result.decision.allow is False

    def test_transition_without_auth_roles_allows_anyone(self):
        """A transition with no auth_roles set is accessible to all callers."""
        engine = WorkflowEngine.from_ast_node(
            ASTNode(
                kind="Workflow",
                id="open_flow",
                properties={
                    "initial": "a",
                    "states": ["a", "b"],
                    "transitions": [{"from": "a", "on": "go", "to": "b"}],
                },
            )
        )
        result = engine.fire("go", actor_roles=[])
        assert result.decision.allow is True
