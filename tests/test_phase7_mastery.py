import time
import pytest
import re
from mpc.features.expr import ExprEngine
from mpc.kernel.meta.models import DomainMeta

def test_vm_performance_simple():
    meta = DomainMeta(kinds=[])
    # A nested addition expression to test recursive depth and speed
    # (1 + (1 + (1 + ...)))
    depth = 100
    expr = "1"
    for _ in range(depth):
        expr = f"(1 + {expr})"
    
    engine_vm = ExprEngine(meta=meta, use_vm=True, max_depth=200)
    engine_rec = ExprEngine(meta=meta, use_vm=False, max_depth=200)
    
    start = time.perf_counter()
    res_vm = engine_vm.evaluate(expr)
    time_vm = time.perf_counter() - start
    
    start = time.perf_counter()
    res_rec = engine_rec.evaluate(expr)
    time_rec = time.perf_counter() - start
    
    print(f"\n[PERF] VM: {time_vm:.6f}s | Recursive: {time_rec:.6f}s")
    assert res_vm.value == depth + 1
    assert res_rec.value == depth + 1

def test_regex_budget_shield():
    meta = DomainMeta(kinds=[])
    engine = ExprEngine(meta=meta, max_regex_ops=2)
    
    # First two should pass
    engine.evaluate('regex("hello", "h.*")')
    engine.evaluate('regex("world", "w.*")')
    
    # Third should trigger budget error
    from mpc.kernel.errors.exceptions import MPCBudgetError
    with pytest.raises(MPCBudgetError) as exc:
        engine.evaluate('regex("fail", "f.*")')
    assert "Regex operation limit exceeded" in str(exc.value)

def test_short_circuit_and_vm():
    meta = DomainMeta(kinds=[])
    engine = ExprEngine(meta=meta, use_vm=True)
    
    # false and something_that_never_runs
    # In VM, JUMP_IF_FALSE should skip the right side
    res = engine.evaluate('false and regex("long_text", ".*")')
    assert res.value == False
    assert res.steps < 5 # Should be very few steps

if __name__ == "__main__":
    # Manual run for perf check
    test_vm_performance_simple()
