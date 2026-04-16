# Release Gate (Repo)

This repository defines a single **release gate** path that is expected to stay green for mainline changes.

## Local (Windows / PowerShell)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/run-release-gate.ps1
```

Skip Studio gates:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/run-release-gate.ps1 -SkipStudio
```

Enforce benchmark thresholds:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/run-release-gate.ps1 -EnforceBenchmarks
```

## What it runs

- `pytest` under `tests/`
- `pytest` under `tooling/mpc-runtime/tests/` (remote runtime gates)
- `mpc-conformance run packages/core-conformance/fixtures/`
- MPC Studio contract + conformance gates (unless `-SkipStudio`)
  - Optional: `npm run test:benchmark:enforce` (when `-EnforceBenchmarks`)

## Notes

- Runtime test suite requires Redis. The gate will use `MPC_RUNTIME_REDIS_URL` if set; otherwise it will try to start a temporary Redis via Docker.

