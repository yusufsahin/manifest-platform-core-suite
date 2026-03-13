"""MPC Full Coverage Example Usage.

This script demonstrates the complete 'Metadriven' lifecycle:
1. Define Domain Metadata (The Schema of Schemas)
2. Author Manifest DSL (Business Logic & Entities)
3. Parse & Validate (Structural & Semantic Integrity)
4. Compile to Registry (Hashed, Immutable Runtime Artifact)
5. Runtime Execution (Workflows, Expressions, and Policies)
"""
import sys
import os
from datetime import datetime

# Ensure we can import from src
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from mpc.kernel.meta.models import DomainMeta, KindDef, FunctionDef
from mpc.kernel.parser import parse
from mpc.tooling.validator.structural import validate_structural
from mpc.tooling.validator.semantic import validate_semantic
from mpc.tooling.registry.compiler import compile_registry
from mpc.features.workflow.fsm import WorkflowEngine
from mpc.features.expr.engine import ExprEngine
from mpc.features.policy.engine import PolicyEngine
from mpc.features.acl.engine import ACLEngine

# ==========================================
# 1. METADRIVEN CONFIGURATION (DomainMeta)
# ==========================================
# We define what 'Kinds' of objects are allowed in our system.
# This makes MPC truly generic.
meta = DomainMeta(
    kinds=[
        KindDef(name="Entity", required_props=["name"]),
        KindDef(name="Attribute", required_props=["type"]),
        KindDef(name="Workflow", required_props=["initial", "states"]),
        KindDef(name="Policy", required_props=["effect", "condition"]),
    ],
    allowed_types=["string", "int", "decimal", "bool", "timestamp"],
    allowed_events=["case.create", "case.update", "case.close"],
    allowed_functions=[
        FunctionDef(name="is_vip", args=["user"], returns="bool"),
        FunctionDef(name="sum", args=["array"], returns="int"),
    ],
)

# ==========================================
# 2. MANIFEST AUTHORING (DSL)
# ==========================================
# Users author business logic using a human-readable DSL.
dsl_content = """
@schema 1
@namespace "enterprise.crm"
@name "customer_onboarding"
@version "1.2.0"

# Defining a Data Entity
def Entity Customer "Global Customer Profile" {
    name: "Customer"
    
    # Nested children
    def Attribute email "Primary Email" {
        type: "string"
        required: true
    }
    
    def Attribute score "Credit Score" {
        type: "int"
        default: 0
    }
}

# Defining a Business Process
def Workflow onboarding "Onboarding Flow" {
    initial: "PROSPECT"
    states: ["PROSPECT", "VERIFYING", "ACTIVE", "REJECTED"]
    finals: ["ACTIVE", "REJECTED"]
    
    transitions: [
        {"from": "PROSPECT", "on": "submit", "to": "VERIFYING", "guard": "has_email"},
        {"from": "VERIFYING", "on": "approve", "to": "ACTIVE", "auth_roles": ["admin"]},
        {"from": "VERIFYING", "on": "reject", "to": "REJECTED"}
    ]
}

# Defining a Security Policy
def Policy allow_admin "Admin Access" {
    effect: "allow"
    condition: {"fn": "is_vip", "args": [{"var": "user"}]}
}
"""

print(f"--- [1/5] Parsing DSL ---")
ast = parse(dsl_content)
print(f"Created AST for namespace '{ast.namespace}' with {len(ast.defs)} definitions.")

# ==========================================
# 3. VALIDATION (Tooling)
# ==========================================
print(f"\n--- [2/5] Validating Structural & Semantic ---")
structural_errors = validate_structural(ast, meta)
semantic_errors = validate_semantic(ast)

if structural_errors or semantic_errors:
    print("Validation Failed!")
    for e in structural_errors + semantic_errors:
        print(f"  [{e.code}] {e.message}")
    sys.exit(1)
print("Validation passed successfully.")

# ==========================================
# 4. COMPILATION (Registry)
# ==========================================
print(f"\n--- [3/5] Compiling Registry ---")
registry = compile_registry(ast, meta)
print(f"Registry Artifact Hash: {registry.artifact_hash}")
print(f"Internal AST Hash: {registry.ast_hash}")
print(f"Dependency Graph: {registry.dependency_graph}")

# ==========================================
# 5. RUNTIME EXECUTION (Features)
# ==========================================
print(f"\n--- [4/5] Running Workflow ---")
wf_node = next(d for d in ast.defs if d.id == "onboarding")
engine = WorkflowEngine.from_ast_node(wf_node)

print(f"Current State: {engine.current_state}")
result = engine.fire("submit", context={"has_email": True})
print(f"Fired 'submit' -> New State: {result.new_state}")


print(f"\n--- [5/5] Authorizing via Policy Engine ---")
policy_node = next(d for d in ast.defs if d.id == "allow_admin")
# Mock an expression function implementation
class MockFunctions:
    def is_vip(self, user):
        return user.get("vip", False)

expr_engine = ExprEngine(functions=MockFunctions())
policy_engine = PolicyEngine(expr_engine=expr_engine)

context = {"user": {"name": "Alice", "vip": True}}
decision = policy_engine.evaluate(policy_node, context)
print(f"Policy Decision for Alice: {decision.effect} (Reason: VIP Status)")

context_bob = {"user": {"name": "Bob", "vip": False}}
decision_bob = policy_engine.evaluate(policy_node, context_bob)
print(f"Policy Decision for Bob: {decision_bob.effect} (Bob is not VIP)")

print("\n--- Full Coverage Demonstration Completed ---")
