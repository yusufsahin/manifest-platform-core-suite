param(
  [switch]$SkipStudio = $false,
  [switch]$EnforceBenchmarks = $false,
  [string]$Python = "python",
  [string]$Node = "node"
)

$ErrorActionPreference = "Stop"

function Exec($cmd) {
  Write-Host ">> $cmd"
  & powershell -NoProfile -Command $cmd
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code $LASTEXITCODE: $cmd"
  }
}

Write-Host "=== RELEASE GATE (repo) ==="

Exec "$Python -m pytest tests -q"
Exec "mpc-conformance run packages/core-conformance/fixtures/"

if (-not $SkipStudio) {
  $studioRoot = Join-Path $PSScriptRoot "..\tooling\mpc-studio"
  if (Test-Path $studioRoot) {
    Exec "cd `"$studioRoot`"; npm run -s test:contracts"
    Exec "cd `"$studioRoot`"; npm run -s test:conformance"
    if ($EnforceBenchmarks) {
      Exec "cd `"$studioRoot`"; npm run -s test:benchmark:enforce"
    }
  } else {
    Write-Host ">> Studio not found; skipping Studio gates."
  }
} else {
  Write-Host ">> Skipping Studio gates (--SkipStudio)."
}

Write-Host "OK: Release gate passed."

