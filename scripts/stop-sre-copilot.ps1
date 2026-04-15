Write-Host "===============================" -ForegroundColor Red
Write-Host "   SRE COPILOT - ARRET" -ForegroundColor Red
Write-Host "==============================="
Write-Host ""

# -------------------------------------------------------
# 1. Tuer tous les port-forwards kubectl
# -------------------------------------------------------
Write-Host "1. Arret des port-forwards kubectl..." -ForegroundColor Yellow
$kubectlProcs = Get-Process -Name "kubectl" -ErrorAction SilentlyContinue
if ($kubectlProcs) {
    $kubectlProcs | Stop-Process -Force
    Write-Host "   $($kubectlProcs.Count) processus kubectl termines." -ForegroundColor Green
} else {
    Write-Host "   Aucun processus kubectl actif." -ForegroundColor Gray
}
Write-Host ""

# -------------------------------------------------------
# 2. Tuer les fenetres PowerShell des port-forwards
#    (celles lancees par start-sre-copilot.ps1)
# -------------------------------------------------------
Write-Host "2. Fermeture des fenetres PowerShell de port-forward..." -ForegroundColor Yellow
$titles = @("Grafana","Prometheus","Alertmanager","n8n","ArgoCD","SRE-Agent","SRE Agent")
$closed = 0
Get-Process -Name "powershell" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $wmi = Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue
        if ($wmi -and ($wmi.CommandLine -match "pf-persistent|port-forward")) {
            $_.Kill()
            $closed++
        }
    } catch {}
}
if ($closed -gt 0) {
    Write-Host "   $closed fenetres PowerShell fermees." -ForegroundColor Green
} else {
    Write-Host "   Aucune fenetre de port-forward detectee." -ForegroundColor Gray
}
Write-Host ""

# -------------------------------------------------------
# 3. Verifier que les ports sont bien liberes
# -------------------------------------------------------
Write-Host "3. Verification des ports..." -ForegroundColor Yellow
$ports = @(3000, 9090, 9093, 5678, 8080, 8001)
$allFree = $true
foreach ($port in $ports) {
    $used = netstat -ano 2>$null | Select-String ":$port\s.*LISTEN"
    if ($used) {
        Write-Host "   Port $port : encore occupe" -ForegroundColor Red
        $allFree = $false
    } else {
        Write-Host "   Port $port : libre" -ForegroundColor Green
    }
}
Write-Host ""

# -------------------------------------------------------
# 4. (Optionnel) Arreter le cluster KinD
# -------------------------------------------------------
Write-Host "4. Arreter le cluster KinD ? (o/n)" -ForegroundColor Cyan
$rep = Read-Host "   Reponse"
if ($rep -eq "o" -or $rep -eq "O" -or $rep -eq "oui") {
    Write-Host "   Arret du cluster sre-cluster..." -ForegroundColor Yellow
    kind delete cluster --name sre-cluster 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Cluster sre-cluster supprime." -ForegroundColor Green
    } else {
        Write-Host "   Echec suppression cluster (deja supprime ?)." -ForegroundColor Red
    }
} else {
    Write-Host "   Cluster KinD conserve (pods toujours en memoire)." -ForegroundColor Gray
}
Write-Host ""

# -------------------------------------------------------
# Recapitulatif
# -------------------------------------------------------
Write-Host "===============================" -ForegroundColor Green
Write-Host "   ARRET TERMINE !" -ForegroundColor Green
Write-Host "==============================="
Write-Host ""
Write-Host "  Port-forwards : arretes"
Write-Host "  Ollama         : toujours actif sur Windows (fermer manuellement si besoin)"
Write-Host "  Docker Desktop : toujours actif (fermer manuellement si besoin)"
if ($rep -ne "o" -and $rep -ne "O" -and $rep -ne "oui") {
    Write-Host "  Cluster KinD   : toujours actif (relancer start-sre-copilot.ps1 pour reconnnecter)"
} else {
    Write-Host "  Cluster KinD   : supprime"
}
Write-Host ""
Write-Host "Pour relancer : .\scripts\start-sre-copilot.ps1" -ForegroundColor Cyan
