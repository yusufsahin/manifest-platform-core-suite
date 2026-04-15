$ErrorActionPreference = "Stop"

Push-Location (Resolve-Path "$PSScriptRoot\..\..\..")

try {
  $env:PYTHONPATH = "src"
  python -m uvicorn tooling.mpc_runtime.app:app --reload --port 8787
} finally {
  Pop-Location
}

