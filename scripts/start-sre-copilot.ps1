Write-Host "==============================="
Write-Host "   SRE COPILOT ENV STARTUP"
Write-Host "==============================="
Write-Host ""

# -------------------------------------------------------
# 0. Nettoyer les anciens port-forwards kubectl
# -------------------------------------------------------
Write-Host "0. Nettoyage des anciens port-forwards..."
$oldPF = Get-Process -Name "kubectl" -ErrorAction SilentlyContinue
if ($oldPF) {
    $oldPF | Stop-Process -Force
    Write-Host "   Anciens processus kubectl termines."
    Start-Sleep -Seconds 2
} else {
    Write-Host "   Aucun port-forward actif."
}
Write-Host ""

# -------------------------------------------------------
# 1. Verifications
# -------------------------------------------------------
Write-Host "1. Verification de Docker..."
docker ps --format "table {{.Names}}\t{{.Status}}" 2>&1 | Select-Object -First 6
Write-Host ""

Write-Host "2. Verification des clusters KIND..."
kind get clusters
Write-Host ""

Write-Host "3. Verification des nodes Kubernetes..."
kubectl get nodes
Write-Host ""

Write-Host "4. Verification des pods monitoring..."
kubectl get pods -n monitoring
Write-Host ""

Write-Host "5. Verification des pods demo..."
kubectl get pods -n demo 2>&1
Write-Host ""

# -------------------------------------------------------
# Helper: attend qu'un port local soit libre
# -------------------------------------------------------
function Wait-PortFree {
    param([int]$Port, [int]$TimeoutSec = 8)
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        $used = netstat -ano 2>$null | Select-String ":$Port\s"
        if (-not $used) { return $true }
        Start-Sleep -Seconds 1
        $elapsed++
    }
    return $false
}

# -------------------------------------------------------
# Helper: lance un port-forward et verifie qu'il demarre
# -------------------------------------------------------
function Start-PortForward {
    param(
        [string]$Label,
        [string]$Service,
        [string]$Namespace,
        [int]$LocalPort,
        [int]$RemotePort,
        [string]$Url
    )
    Write-Host "   Port-forward $Label ($LocalPort -> $RemotePort)..."

    # Verifier que le port est libre
    $free = Wait-PortFree -Port $LocalPort -TimeoutSec 5
    if (-not $free) {
        Write-Host "   ATTENTION: port $LocalPort toujours occupe, tentative quand meme..." -ForegroundColor Yellow
    }

    $cmd = "kubectl port-forward svc/$Service -n $Namespace ${LocalPort}:${RemotePort}"
    Start-Process powershell -ArgumentList "-NoExit -Command $cmd"
    Start-Sleep -Seconds 3

    # Verifier que le port est bien ouvert
    $listening = netstat -ano 2>$null | Select-String ":$LocalPort\s.*LISTEN"
    if ($listening) {
        Write-Host "   OK  $Label -> $Url" -ForegroundColor Green
    } else {
        Write-Host "   ECHEC $Label sur port $LocalPort (verifier la fenetre PowerShell)" -ForegroundColor Red
    }
    Write-Host ""
}

# -------------------------------------------------------
# 6. Port-forwards
# -------------------------------------------------------
Write-Host "6. Demarrage des port-forwards..."
Write-Host ""

Start-PortForward -Label "Grafana" `
    -Service "monitoring-grafana" `
    -Namespace "monitoring" `
    -LocalPort 3000 -RemotePort 80 `
    -Url "http://localhost:3000"

Start-PortForward -Label "Prometheus" `
    -Service "monitoring-kube-prometheus-prometheus" `
    -Namespace "monitoring" `
    -LocalPort 9090 -RemotePort 9090 `
    -Url "http://localhost:9090"

Start-PortForward -Label "Alertmanager" `
    -Service "monitoring-kube-prometheus-alertmanager" `
    -Namespace "monitoring" `
    -LocalPort 9093 -RemotePort 9093 `
    -Url "http://localhost:9093"

Start-PortForward -Label "n8n" `
    -Service "n8n-service" `
    -Namespace "n8n" `
    -LocalPort 5678 -RemotePort 5678 `
    -Url "http://localhost:5678"

Start-PortForward -Label "ArgoCD" `
    -Service "argocd-server" `
    -Namespace "argocd" `
    -LocalPort 8080 -RemotePort 80 `
    -Url "http://localhost:8080"

Start-PortForward -Label "SRE Agent" `
    -Service "sre-agent-service" `
    -Namespace "sre-agent" `
    -LocalPort 8001 -RemotePort 8000 `
    -Url "http://localhost:8001"

# -------------------------------------------------------
# 7. Ouvrir les navigateurs
# -------------------------------------------------------
Write-Host "Ouverture des navigateurs..."
Start-Sleep -Seconds 1
Start-Process "http://localhost:3000"
Start-Process "http://localhost:9090"
Start-Process "http://localhost:5678"
Start-Process "http://localhost:8080"

# -------------------------------------------------------
# Recapitulatif
# -------------------------------------------------------
Write-Host "==============================="
Write-Host "   ENVIRONNEMENT PRET !"
Write-Host "==============================="
Write-Host ""
Write-Host "  Grafana      -> http://localhost:3000  (admin / prom-operator)"
Write-Host "  Prometheus   -> http://localhost:9090"
Write-Host "  Alertmanager -> http://localhost:9093"
Write-Host "  n8n          -> http://localhost:5678"
Write-Host "  ArgoCD       -> http://localhost:8080"
Write-Host "  SRE Agent    -> http://localhost:8001  (API) | http://localhost:8001/docs (Swagger)"
Write-Host ""
Write-Host "IMPORTANT: Ne ferme pas les fenetres PowerShell des port-forwards !"
