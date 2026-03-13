import sys
from mpc.features.expr.engine import ExprEngine
from mpc.kernel.meta.models import DomainMeta
from mpc.kernel.meta.diff import diff_meta
print("Python version:", sys.version)
print("Import successful!")
meta = DomainMeta(allowed_functions=[])
engine = ExprEngine(meta=meta)
res = engine.evaluate("42")
print("Evaluation result:", res.value)
assert res.value == 42
print("Assertion passed!")
