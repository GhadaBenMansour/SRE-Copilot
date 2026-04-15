Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   SRE COPILOT - DEPLOIEMENT DE L'AGENT IA" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Build Docker image
Write-Host "[1/6] Build de l'image Docker du SRE Agent..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\sre-agent"
docker build -t sre-agent:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERREUR: Docker build a echoue" -ForegroundColor Red
    exit 1
}
Write-Host "   Image sre-agent:latest construite" -ForegroundColor Green

# ── 2. Load image into KinD
Write-Host ""
Write-Host "[2/6] Chargement de l'image dans KinD..." -ForegroundColor Yellow
kind load docker-image sre-agent:latest --name sre-cluster
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERREUR: kind load a echoue. Le cluster sre-cluster est-il demarré ?" -ForegroundColor Red
    exit 1
}
Write-Host "   Image chargée dans le cluster KinD" -ForegroundColor Green

# ── 3. Create namespace and deploy
Write-Host ""
Write-Host "[3/6] Déploiement du SRE Agent dans Kubernetes..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\.."
kubectl apply -f sre-agent-deploy.yaml
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERREUR: kubectl apply a echoue" -ForegroundColor Red
    exit 1
}
Write-Host "   SRE Agent déployé" -ForegroundColor Green

# ── 4. Create kubeconfig secret for in-cluster kubectl access
Write-Host ""
Write-Host "[4/6] Creation du secret kubeconfig pour l'agent..." -ForegroundColor Yellow
$kubeconfigPath = "$env:USERPROFILE\.kube\config"
if (Test-Path $kubeconfigPath) {
    kubectl create secret generic sre-agent-kubeconfig `
        --from-file=config=$kubeconfigPath `
        -n sre-agent `
        --dry-run=client -o yaml | kubectl apply -f -
    Write-Host "   Secret kubeconfig créé/mis à jour" -ForegroundColor Green
} else {
    Write-Host "   AVERTISSEMENT: ~/.kube/config non trouvé, l'agent ne pourra pas faire de kubectl" -ForegroundColor Yellow
}

# ── 5. Wait for pod to be ready
Write-Host ""
Write-Host "[5/6] Attente que le pod sre-agent soit Ready..." -ForegroundColor Yellow
kubectl rollout status deployment/sre-agent -n sre-agent --timeout=120s
if ($LASTEXITCODE -ne 0) {
    Write-Host "AVERTISSEMENT: Timeout. Vérifiez les logs:" -ForegroundColor Yellow
    Write-Host "   kubectl logs -n sre-agent -l app=sre-agent" -ForegroundColor Gray
} else {
    Write-Host "   SRE Agent est prêt !" -ForegroundColor Green
}

# ── 6. Port-forward
Write-Host ""
Write-Host "[6/6] Lancement du port-forward vers le SRE Agent..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command kubectl port-forward svc/sre-agent-service -n sre-agent 8000:8000"
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "   SRE AGENT DEPLOYE ET ACCESSIBLE !" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  API:         http://localhost:8000" -ForegroundColor White
Write-Host "  Health:      http://localhost:8000/health" -ForegroundColor White
Write-Host "  Status:      http://localhost:8000/status" -ForegroundColor White
Write-Host "  Docs:        http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Test crash:  http://localhost:8000/test-crash-loop  (POST)" -ForegroundColor White
Write-Host ""
Write-Host "PROCHAINES ETAPES:" -ForegroundColor Cyan
Write-Host "  1. Importer le workflow n8n:  n8n-workflows/sre-alert-workflow.json" -ForegroundColor Gray
Write-Host "  2. Vérifier Ollama+Mistral:   curl http://localhost:11434/api/tags" -ForegroundColor Gray
Write-Host "  3. Tester l'agent:            Invoke-RestMethod -Uri http://localhost:8000/test-crash-loop -Method POST" -ForegroundColor Gray
Write-Host ""
