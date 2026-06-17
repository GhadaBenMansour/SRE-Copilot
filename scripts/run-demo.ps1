# run-demo.ps1
# Lance UNE démo propre du pipeline SRE Copilot.
#
# Prérequis : la stack doit déjà tourner (.\scripts\start-sre-copilot.ps1 OK).
# Recommandé : faire .\scripts\reset-demo.ps1 juste avant pour partir propre.
#
# Ce qu'il fait :
#   1. Vérifie que la stack est saine (health checks)
#   2. Supprime tous les silences Alertmanager
#   3. Déploie crash-app (replicas=1)
#   4. Ouvre la dashboard
#   5. Suit les logs SRE Agent en direct (Ctrl+C pour quitter)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "===============================" -ForegroundColor Cyan
Write-Host "  DEMO SRE COPILOT" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Health checks rapides
Write-Host "[1] Verification de la stack..." -ForegroundColor Cyan
$checks = @(
    @{Name='SRE Agent'   ; Url='http://localhost:8001/health'},
    @{Name='Prometheus'  ; Url='http://localhost:9090/-/healthy'},
    @{Name='Alertmanager'; Url='http://localhost:9093/-/healthy'},
    @{Name='n8n'         ; Url='http://localhost:5678/healthz'},
    @{Name='Grafana'     ; Url='http://localhost:3000/api/health'}
)
$allOk = $true
foreach ($c in $checks) {
    try {
        Invoke-WebRequest $c.Url -TimeoutSec 5 -ErrorAction Stop | Out-Null
        Write-Host "    OK   $($c.Name)" -ForegroundColor Green
    } catch {
        Write-Host "    FAIL $($c.Name) — relance start-sre-copilot.ps1" -ForegroundColor Red
        $allOk = $false
    }
}
if (-not $allOk) {
    Write-Host ""
    Write-Host "Stack pas prete. Arret." -ForegroundColor Red
    exit 1
}

# ── 2. Supprimer tous les silences (pour que les alertes passent)
Write-Host ""
Write-Host "[2] Suppression des silences Alertmanager..." -ForegroundColor Cyan
try {
    $silences = (Invoke-WebRequest 'http://localhost:9093/api/v2/silences' -TimeoutSec 5).Content | ConvertFrom-Json
    $active = $silences | Where-Object { $_.status.state -eq 'active' }
    foreach ($s in $active) {
        Invoke-WebRequest "http://localhost:9093/api/v2/silence/$($s.id)" -Method DELETE -TimeoutSec 5 | Out-Null
    }
    Write-Host "    $($active.Count) silence(s) leve(s)" -ForegroundColor Green
} catch {
    Write-Host "    (aucun silence)" -ForegroundColor Gray
}

# ── 3. Deployer crash-app
Write-Host ""
Write-Host "[3] Deploiement crash-app..." -ForegroundColor Cyan
kubectl apply -f "$PSScriptRoot\..\demo-app.yaml" 2>&1 | Out-Null
kubectl scale deployment crash-app -n demo --replicas=1 2>&1 | Out-Null
Write-Host "    crash-app deploye. Attente du CrashLoopBackOff (~90s)..." -ForegroundColor Yellow

# Attendre que le pod entre en CrashLoopBackOff
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 5
    $state = kubectl get pods -n demo -l app=crash-app -o jsonpath='{.items[0].status.containerStatuses[0].state}' 2>&1
    if ($state -match 'waiting') {
        $reason = kubectl get pods -n demo -l app=crash-app -o jsonpath='{.items[0].status.containerStatuses[0].state.waiting.reason}' 2>&1
        if ($reason -eq 'CrashLoopBackOff') {
            Write-Host "    crash-app en CrashLoopBackOff ✓" -ForegroundColor Green
            $ready = $true
            break
        }
    }
    Write-Host "    ($($i*5)s) Attente..." -ForegroundColor Gray
}
if (-not $ready) {
    Write-Host "    crash-app pas en CrashLoopBackOff apres 150s. Verifie : kubectl get pods -n demo" -ForegroundColor Yellow
}

# ── 4. Ouvrir la dashboard et n8n executions
Write-Host ""
Write-Host "[4] Ouverture dashboard..." -ForegroundColor Cyan
Start-Process 'http://localhost:8001/dashboard'
Start-Process 'http://localhost:5678/executions'

# ── 5. Suivre les logs SRE Agent
Write-Host ""
Write-Host "===============================" -ForegroundColor Green
Write-Host "  DEMO EN COURS" -ForegroundColor Green
Write-Host "===============================" -ForegroundColor Green
Write-Host ""
Write-Host "  L'alerte Prometheus va monter dans 30-60s (group_wait: 1m)" -ForegroundColor Cyan
Write-Host "  Puis n8n appelle le SRE Agent" -ForegroundColor Cyan
Write-Host "  Investigation Mistral : 150-250 secondes" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Logs en direct ci-dessous (Ctrl+C pour quitter) :" -ForegroundColor Yellow
Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor Yellow
kubectl logs -f deployment/sre-agent -n sre-agent --tail=5
