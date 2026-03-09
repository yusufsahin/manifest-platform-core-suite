"""Getting started with MPC — a complete example in under 50 lines.

This example demonstrates:
1. Defining a DomainMeta (what constructs are allowed)
2. Parsing a manifest from DSL
3. Validating the manifest
4. Compiling to an immutable registry
5. Evaluating expressions
6. Running a workflow
7. Checking ACL rules
"""
from mpc.meta.models import DomainMeta, KindDef, FunctionDef
from mpc.parser import parse
from mpc.validator import validate_structural, validate_semantic
from mpc.registry.compiler import compile_registry
from mpc.expr import ExprEngine
from mpc.workflow import WorkflowEngine

# 1. Define your domain
meta = DomainMeta(
    kinds=[
        KindDef(name="Entity", required_props=["name"]),
        KindDef(name="Workflow", required_props=["initial"]),
    ],
    allowed_types=["string", "int", "bool", "array"],
    allowed_functions=[
        FunctionDef(name="len", args=["string"], returns="int"),
        FunctionDef(name="upper", args=["string"], returns="string"),
    ],
)

# 2. Parse a manifest
manifest_dsl = """
@schema 1
@namespace "myapp"
@name "example"
@version "1.0"

def Entity user "User" {
    name: "User"
    maxLength: 50
    active: true
}

def Workflow approval "Approval Flow" {
    initial: "pending"
    states: ["pending", "approved", "rejected"]
    finals: ["approved", "rejected"]
    transitions: [
        {"from": "pending", "on": "approve", "to": "approved"},
        {"from": "pending", "on": "reject", "to": "rejected"}
    ]
}
"""

ast = parse(manifest_dsl)
print(f"Parsed {len(ast.defs)} definitions from '{ast.name}'")

# 3. Validate
structural_errors = validate_structural(ast, meta)
semantic_errors = validate_semantic(ast)
print(f"Structural errors: {len(structural_errors)}, Semantic errors: {len(semantic_errors)}")

# 4. Compile
registry = compile_registry(ast, meta)
print(f"Compiled registry — artifact hash: {registry.artifact_hash[:16]}...")

# 5. Evaluate an expression
engine = ExprEngine(meta=meta)
result = engine.evaluate({"fn": "len", "args": [{"lit": "Hello MPC"}]})
print(f"len('Hello MPC') = {result.value}")

# 6. Run a workflow
wf_node = next(d for d in ast.defs if d.kind == "Workflow")
wf = WorkflowEngine.from_ast_node(wf_node)
print(f"Workflow state: {wf.current_state}")

fire_result = wf.fire("approve")
print(f"After 'approve': state={fire_result.new_state}, allowed={fire_result.decision.allow}")
