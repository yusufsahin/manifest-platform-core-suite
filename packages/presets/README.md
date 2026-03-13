# MPC Presets

Presets are pre-configured domain-agnostic meta-definitions, limits, and policies used to bootstrap an MPC engine instance.

## Available Presets

- `preset-generic-min`: Minimal configuration with basic scalar types.
- `preset-generic-full`: Full feature set including all standard functions and kinds.
- `preset-security-hardened`: Strict budget limits and disabled unsafe functions (e.g. `now()`).
- `preset-ui-friendly`: Includes metadata hints optimized for UI schema generation.

## Usage

In your consuming application:

```python
from mpc.kernel.parser import parse
from mpc.kernel.meta import DomainMeta

# Load your domain meta
meta = DomainMeta(...)

# Presets effectively define the 'Standard Library' available to your manifests
```

## Structure

Each preset defines:
1. **Allowed Kinds**: (Workflow, Policy, ACL, etc.)
2. **Allowed Functions**: (arithmetic, string, regex, collections)
3. **Budget Limits**: (max_steps, max_depth, timeout)
4. **Ordering Rules**: Deterministic canonicalization rules.
