import pytest
from mpc.features.redaction import RedactionEngine, RedactionConfig
from mpc.kernel.contracts.models import Error
from mpc.kernel.meta.diff import detect_drift
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.kernel.ast.models import ManifestAST, ASTNode

def test_redaction_dataclass():
    engine = RedactionEngine(config=RedactionConfig(deny_keys=frozenset({"secret"})))
    err = Error(code="E_TEST", message="Test", severity="error", properties={"secret": "password123"})
    
    # redacted result should be a dict
    res = engine.redact(err)
    assert isinstance(res, dict)
    assert res["properties"]["secret"] == "***"
    assert res["code"] == "E_TEST"

def test_drift_detection():
    meta = DomainMeta(kinds=[
        KindDef(name="Workflow", required_props=["initial"], optional_props=["states"])
    ])
    
    # Valid AST
    ast_ok = ManifestAST(schema_version=1, namespace="ns", name="ok", defs=[
        ASTNode(kind="Workflow", id="w1", properties={"initial": "S1", "states": ["S1"]})
    ])
    assert detect_drift(ast_ok, meta) == []
    
    # Drift: Unknown Kind
    ast_drift1 = ManifestAST(schema_version=1, namespace="ns", name="drift1", defs=[
        ASTNode(kind="UnknownKind", id="u1", properties={})
    ])
    drifts = detect_drift(ast_drift1, meta)
    assert len(drifts) == 1
    assert "Kind 'UnknownKind' is not in DomainMeta" in drifts[0]
    
    # Drift: Unknown Property
    ast_drift2 = ManifestAST(schema_version=1, namespace="ns", name="drift2", defs=[
        ASTNode(kind="Workflow", id="w2", properties={"initial": "S1", "extra_prop": 42})
    ])
    drifts = detect_drift(ast_drift2, meta)
    assert len(drifts) == 1
    assert "Property 'extra_prop' is not defined for kind 'Workflow'" in drifts[0]

def test_redact_exception():
    engine = RedactionEngine(config=RedactionConfig(deny_keys=frozenset({"apiKey"})))
    try:
        raise ValueError("Failed with apiKey='12345'")
    except Exception as e:
        redacted = engine.redact_exception(e)
        assert "[REDACTED TRACE LINE]" in redacted
