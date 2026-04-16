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
    throw "Command failed with exit code ${LASTEXITCODE}: $cmd"
  }
}

function EnsureRedisForRuntimeTests() {
  if ($env:MPC_RUNTIME_REDIS_URL -and $env:MPC_RUNTIME_REDIS_URL.Trim().Length -gt 0) {
    Write-Host ">> Using MPC_RUNTIME_REDIS_URL=$env:MPC_RUNTIME_REDIS_URL"
    return @{ started = $false; container = $null }
  }

  # Try to start a local Redis via Docker for the gate.
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    throw "MPC_RUNTIME_REDIS_URL is not set and Docker is not available. Start Redis or set MPC_RUNTIME_REDIS_URL."
  }

  $name = "mpc-runtime-redis-gate"
  Write-Host ">> Starting Redis via Docker ($name)"
  cmd /c "docker rm -f $name >NUL 2>NUL"
  Exec "docker run -d --name $name -p 6379:6379 redis:7-alpine"
  $env:MPC_RUNTIME_REDIS_URL = "redis://localhost:6379/0"
  Start-Sleep -Seconds 2
  return @{ started = $true; container = $name }
}

Write-Host "=== RELEASE GATE (repo) ==="

Exec "$Python -m pytest tests -q"

$redisInfo = EnsureRedisForRuntimeTests
try {
  Exec "`$env:MPC_RUNTIME_REQUIRE_REDIS_TESTS='true'; $Python -m pytest tooling/mpc-runtime/tests -q"
} finally {
  if ($redisInfo.started -and $redisInfo.container) {
    Write-Host ">> Stopping Redis Docker container ($($redisInfo.container))"
    cmd /c "docker rm -f $($redisInfo.container) >NUL 2>NUL"
  }
}

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

