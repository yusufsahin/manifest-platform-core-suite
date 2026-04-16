# Release Gate (Repo)

This repository defines a single **release gate** path that is expected to stay green for mainline changes.

## Local (Windows / PowerShell)

```powershell
pwsh -File tools/run-release-gate.ps1
```

Skip Studio gates:

```powershell
pwsh -File tools/run-release-gate.ps1 -SkipStudio
```

Enforce benchmark thresholds:

```powershell
pwsh -File tools/run-release-gate.ps1 -EnforceBenchmarks
```

## What it runs

- `pytest` under `tests/`
- `mpc-conformance run packages/core-conformance/fixtures/`
- MPC Studio contract + conformance gates (unless `-SkipStudio`)
  - Optional: `npm run test:benchmark:enforce` (when `-EnforceBenchmarks`)

