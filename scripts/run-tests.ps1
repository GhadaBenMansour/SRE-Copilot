# run-tests.ps1
# Lance la suite pytest du SRE Agent (tests unitaires + FastAPI).
# Aucun cluster ni Ollama necessaire — tout est mocke.
#
# Usage :
#   .\scripts\run-tests.ps1              # tous les tests
#   .\scripts\run-tests.ps1 -Verbose     # avec sortie verbeuse
#   .\scripts\run-tests.ps1 -File test_agent.py  # un seul fichier

param(
    [switch]$Verbose,
    [string]$File = ""
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "===============================" -ForegroundColor Cyan
Write-Host "  SRE COPILOT - TEST SUITE" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan
Write-Host ""

# Verifier que pytest est installe
$pytestVersion = python -m pytest --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] pytest absent — installation..." -ForegroundColor Yellow
    pip install pytest==8.3.4 pytest-asyncio==0.25.0 2>&1 | Select-Object -Last 3
}

# Verifier que les dependances du projet sont la
Write-Host "[*] Verification des dependances..." -ForegroundColor Cyan
$check = python -c "import fastapi, pydantic, prometheus_client; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Installation des dependances projet..." -ForegroundColor Yellow
    pip install -r "$PSScriptRoot\..\sre-agent\requirements.txt" 2>&1 | Select-Object -Last 3
}
Write-Host "    Dependances OK" -ForegroundColor Green
Write-Host ""

# Lancer pytest depuis le dossier sre-agent/ (pour que les imports relatifs marchent)
$sreAgentDir = Join-Path $PSScriptRoot ".." "sre-agent"
$sreAgentDir = (Resolve-Path $sreAgentDir).Path
Push-Location $sreAgentDir
try {
    $args = @()
    if ($File) {
        $args += "tests/$File"
    } else {
        $args += "tests/"
    }
    if ($Verbose) { $args += "-vv" }

    Write-Host "[*] Execution : python -m pytest $($args -join ' ')" -ForegroundColor Cyan
    Write-Host ""
    python -m pytest @args
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "===============================" -ForegroundColor Green
    Write-Host "  TOUS LES TESTS PASSENT !" -ForegroundColor Green
    Write-Host "===============================" -ForegroundColor Green
} else {
    Write-Host "===============================" -ForegroundColor Red
    Write-Host "  TESTS EN ECHEC ($exitCode)" -ForegroundColor Red
    Write-Host "===============================" -ForegroundColor Red
}
exit $exitCode
