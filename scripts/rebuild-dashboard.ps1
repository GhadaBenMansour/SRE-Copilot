# rebuild-dashboard.ps1
# Rebuild + redeploy le SRE Agent apres une modification de html_pages.py ou main.py
# Usage : .\scripts\rebuild-dashboard.ps1

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host ""
Write-Host "┌─────────────────────────────────────────┐" -ForegroundColor Cyan
Write-Host "│   SRE Copilot — Rebuild & Redeploy      │" -ForegroundColor Cyan
Write-Host "└─────────────────────────────────────────┘" -ForegroundColor Cyan
Write-Host ""

# 1. Build Docker
Write-Host "[1/3] Build Docker image..." -ForegroundColor Yellow
docker build -t sre-agent:latest ./sre-agent
if ($LASTEXITCODE -ne 0) { Write-Host "ERREUR build Docker" -ForegroundColor Red; exit 1 }
Write-Host "      OK" -ForegroundColor Green

# 2. Load dans KinD
Write-Host "[2/3] Chargement dans KinD..." -ForegroundColor Yellow
kind load docker-image sre-agent:latest --name sre-cluster
if ($LASTEXITCODE -ne 0) { Write-Host "ERREUR kind load" -ForegroundColor Red; exit 1 }
Write-Host "      OK" -ForegroundColor Green

# 3. Rollout restart
Write-Host "[3/3] Redemarrage du pod..." -ForegroundColor Yellow
kubectl rollout restart deployment/sre-agent -n sre-agent
kubectl rollout status deployment/sre-agent -n sre-agent --timeout=90s
if ($LASTEXITCODE -ne 0) { Write-Host "ERREUR rollout" -ForegroundColor Red; exit 1 }
Write-Host "      OK" -ForegroundColor Green

# 4. Relancer le port-forward si necessaire
$pf = Get-Process -Name "kubectl" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*port-forward*" }
if (-not $pf) {
    Write-Host ""
    Write-Host "[+] Relance du port-forward (8001→8000)..." -ForegroundColor Yellow
    Start-Process -NoNewWindow kubectl -ArgumentList "port-forward service/sre-agent-service 8001:8000 -n sre-agent"
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "✓ Dashboard mis a jour : http://localhost:8001/dashboard" -ForegroundColor Green
Write-Host ""
