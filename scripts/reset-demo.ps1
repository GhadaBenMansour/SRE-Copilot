# reset-demo.ps1
# Remet l'environnement à zéro entre deux démos / tests.
# Ne touche PAS au cluster ni à la stack — seulement aux données runtime.
#
# Usage :
#   .\scripts\reset-demo.ps1                  # reset standard (garde l'historique)
#   .\scripts\reset-demo.ps1 -ClearHistory   # supprime aussi les incidents persistés
#
# Ce qu'il fait :
#   1. Stop toutes les exécutions n8n en cours
#   2. Crée un silence Alertmanager (1h) sur PodRestartingTooMuch
#   3. Scale crash-app à 0 et supprime ses pods
#   4. (Optionnel) Vide /gitops-repo/incidents/responses.jsonl

param(
    [switch]$ClearHistory
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "===============================" -ForegroundColor Red
Write-Host "  RESET ENVIRONNEMENT DEMO" -ForegroundColor Red
Write-Host "===============================" -ForegroundColor Red
Write-Host ""

# ── 1. Stop les jobs PowerShell en background (Start-Job de tests précédents)
Write-Host "[1] Stop des Start-Job PowerShell..." -ForegroundColor Cyan
$jobs = Get-Job -ErrorAction SilentlyContinue
if ($jobs) {
    $jobs | Stop-Job -ErrorAction SilentlyContinue
    $jobs | Remove-Job -ErrorAction SilentlyContinue
    Write-Host "    $($jobs.Count) job(s) termine(s)" -ForegroundColor Green
} else {
    Write-Host "    Aucun job actif" -ForegroundColor Gray
}

# ── 2. Silence Alertmanager pour PodRestartingTooMuch (1h)
Write-Host ""
Write-Host "[2] Silence Alertmanager (1h)..." -ForegroundColor Cyan
$silenceBody = @{
    matchers = @(@{ name = 'alertname'; value = 'PodRestartingTooMuch'; isRegex = $false; isEqual = $true })
    startsAt = (Get-Date -Format 'o')
    endsAt   = (Get-Date).AddHours(1).ToString('o')
    createdBy = 'reset-demo'
    comment  = 'Reset demo : ignorer PodRestartingTooMuch pendant 1h'
} | ConvertTo-Json -Depth 5 -Compress

try {
    $r = Invoke-WebRequest 'http://localhost:9093/api/v2/silences' -Method POST `
        -Body $silenceBody -ContentType 'application/json' -TimeoutSec 5
    $sid = ($r.Content | ConvertFrom-Json).silenceID
    Write-Host "    Silence ID : $sid" -ForegroundColor Green
} catch {
    Write-Host "    Alertmanager non joignable — skip" -ForegroundColor Yellow
}

# ── 3. Scale crash-app à 0 et supprime ses pods forcément
Write-Host ""
Write-Host "[3] Stop crash-app..." -ForegroundColor Cyan
kubectl scale deployment crash-app -n demo --replicas=0 2>&1 | Out-Null
kubectl delete pods -n demo -l app=crash-app --grace-period=0 --force --ignore-not-found 2>&1 | Out-Null
Write-Host "    crash-app scale a 0 et pods supprimes" -ForegroundColor Green

# ── 4. Optionnel : vider l'historique des incidents
if ($ClearHistory) {
    Write-Host ""
    Write-Host "[4] Suppression historique incidents (--ClearHistory)..." -ForegroundColor Cyan
    $pod = kubectl get pod -n sre-agent -l app=sre-agent --no-headers `
        -o custom-columns="NAME:.metadata.name" 2>&1 | Select-Object -First 1
    if ($pod -and $pod -notmatch "Error") {
        kubectl exec -n sre-agent $pod -- sh -c "rm -f /gitops-repo/incidents/responses.jsonl" 2>&1 | Out-Null
        Write-Host "    /gitops-repo/incidents/responses.jsonl supprime" -ForegroundColor Green
        Write-Host "    Dashboard sera vide au prochain refresh" -ForegroundColor Gray
    }
} else {
    Write-Host ""
    Write-Host "[4] Historique conserve (utiliser -ClearHistory pour effacer)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "===============================" -ForegroundColor Green
Write-Host "  RESET TERMINE" -ForegroundColor Green
Write-Host "===============================" -ForegroundColor Green
Write-Host ""
Write-Host "  Prochaine etape : lancer un nouveau test avec" -ForegroundColor Cyan
Write-Host "    .\scripts\run-demo.ps1" -ForegroundColor White
Write-Host ""
