Write-Host "===============================" -ForegroundColor Cyan
Write-Host "   SRE COPILOT ENV STARTUP" -ForegroundColor Cyan
Write-Host "==============================="
Write-Host ""

# -------------------------------------------------------
# 0. Tuer les anciens port-forwards kubectl
# -------------------------------------------------------
Write-Host "[0] Nettoyage des anciens port-forwards..." -ForegroundColor Yellow
Get-Process -Name "kubectl" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Write-Host "    OK" -ForegroundColor Green
Write-Host ""

# -------------------------------------------------------
# 0b. Verifier / recreer le cluster KinD
# -------------------------------------------------------
Write-Host "[0b] Verification du cluster KinD..." -ForegroundColor Cyan
$kindClusters = kind get clusters 2>&1
$needsDeploy = $false

if ($kindClusters -notmatch "sre-cluster") {
    Write-Host "    Cluster absent - recreation..." -ForegroundColor Yellow
    kind create cluster --name sre-cluster --config "$PSScriptRoot\..\kind-cluster.yaml" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    ERREUR: impossible de creer le cluster. Verifie Docker Desktop." -ForegroundColor Red
        exit 1
    }
    Write-Host "    Cluster cree (port API: 6550)." -ForegroundColor Green
    $needsDeploy = $true
} else {
    kind export kubeconfig --name sre-cluster 2>&1 | Out-Null
    $testKubectl = kubectl get nodes --request-timeout=8s 2>&1
    if ($testKubectl -notmatch "Ready") {
        Write-Host "    API server inaccessible - attente 20s..." -ForegroundColor Yellow
        Start-Sleep -Seconds 20
        docker restart sre-cluster-control-plane 2>&1 | Out-Null
        Start-Sleep -Seconds 30
    }
    $monPods = kubectl get pods -n monitoring --no-headers 2>&1
    if (-not $monPods -or $monPods -match "No resources") {
        Write-Host "    Cluster vide - redeploi necessaire." -ForegroundColor Yellow
        $needsDeploy = $true
    } else {
        Write-Host "    Cluster OK avec services deployes." -ForegroundColor Green
    }
}
Write-Host ""

# -------------------------------------------------------
# 1. Redeploi complet si necessaire
# -------------------------------------------------------
if ($needsDeploy) {
    Write-Host "[1] Deploiement complet de la stack..." -ForegroundColor Cyan
    Write-Host ""

    kubectl create namespace monitoring 2>&1 | Out-Null
    kubectl create namespace argocd     2>&1 | Out-Null
    kubectl create namespace n8n        2>&1 | Out-Null
    kubectl create namespace sre-agent  2>&1 | Out-Null
    kubectl create namespace demo       2>&1 | Out-Null
    Write-Host "    Namespaces crees." -ForegroundColor Green

    Write-Host "    kube-prometheus-stack (3-5 min)..." -ForegroundColor Yellow
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>&1 | Out-Null
    helm repo update 2>&1 | Out-Null
    helm install monitoring prometheus-community/kube-prometheus-stack `
        -n monitoring `
        --set grafana.adminPassword=prom-operator `
        --set prometheus.prometheusSpec.retention=1h `
        --timeout 10m 2>&1 | Out-Null
    Write-Host "    kube-prometheus-stack OK." -ForegroundColor Green

    Write-Host "    ArgoCD..." -ForegroundColor Yellow
    kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml 2>&1 | Out-Null
    kubectl wait --for=condition=Available deployment/argocd-server -n argocd --timeout=120s 2>&1 | Out-Null

    # Fixer le mot de passe ArgoCD : admin / Sre@Copilot2026 (hash bcrypt permanent)
    $ARGOCD_HASH = '$2b$10$SGAG3UFmyEB.kOw0xTZVQ.9y3YAIr93kvV/JHMSoJ.wx60RkCilWO'
    $HASH_B64  = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($ARGOCD_HASH))
    $MTIME_B64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((Get-Date -UFormat %s)))
    kubectl patch secret argocd-secret -n argocd `
        --type='json' `
        -p="[{`"op`":`"replace`",`"path`":`"/data/admin.password`",`"value`":`"$HASH_B64`"},{`"op`":`"replace`",`"path`":`"/data/admin.passwordMtime`",`"value`":`"$MTIME_B64`"}]" 2>&1 | Out-Null
    kubectl rollout restart deployment argocd-server -n argocd 2>&1 | Out-Null
    kubectl rollout status deployment argocd-server -n argocd --timeout=120s 2>&1 | Out-Null
    Write-Host "    ArgoCD OK (admin / Sre@Copilot2026)." -ForegroundColor Green

    # Desactiver applicationset-controller (CRD manquante = CrashLoopBackOff perpetuel,
    # mais on n'utilise pas les ApplicationSet — voir defense PFE). Scale a 0.
    kubectl scale deployment argocd-applicationset-controller -n argocd --replicas=0 2>&1 | Out-Null
    Write-Host "    applicationset-controller desactive (non utilise dans le projet)." -ForegroundColor Gray

    # ── ArgoCD : RBAC sre-copilot + Application demo-app (AVANT le SRE Agent) ──
    Write-Host "    ArgoCD RBAC + Application demo-app..." -ForegroundColor Yellow
    kubectl patch configmap argocd-cm -n argocd --type merge `
        -p '{"data":{"accounts.sre-copilot":"apiKey"}}' 2>&1 | Out-Null
    kubectl apply -f "$PSScriptRoot\..\argocd\rbac-cm-patch.yaml" 2>&1 | Out-Null
    kubectl apply -f "$PSScriptRoot\..\argocd\demo-app-application.yaml" 2>&1 | Out-Null
    kubectl rollout restart deployment argocd-server -n argocd 2>&1 | Out-Null
    kubectl rollout status deployment argocd-server -n argocd --timeout=120s 2>&1 | Out-Null
    Write-Host "    ArgoCD RBAC + Application demo-app appliques." -ForegroundColor Green

    # ── Generer + injecter le token ArgoCD permanent (Secret sre-agent-secrets) ──
    Write-Host "    Token ArgoCD permanent (sre-copilot:apiKey)..." -ForegroundColor Yellow
    kubectl create namespace sre-agent --dry-run=client -o yaml | kubectl apply -f - 2>&1 | Out-Null
    & "$PSScriptRoot\generate-argocd-token.ps1" 2>&1 | Where-Object { $_ -match 'Token verified|Done|Token sub|ERREUR|Error' } | ForEach-Object { "      $_" }
    Write-Host "    Token ArgoCD injecte dans sre-agent-secrets." -ForegroundColor Green

    Write-Host "    Applications Kubernetes (demo-app + PrometheusRule)..." -ForegroundColor Yellow
    kubectl apply -f "$PSScriptRoot\..\demo-app.yaml"          2>&1 | Out-Null
    kubectl apply -f "$PSScriptRoot\..\pod-restart-alert.yaml" 2>&1 | Out-Null

    Write-Host "    Alertmanager config (demo namespace seulement)..." -ForegroundColor Yellow
    kubectl create secret generic alertmanager-monitoring-kube-prometheus-alertmanager `
        --from-file=alertmanager.yaml="$PSScriptRoot\..\alertmanager-config.yaml" `
        -n monitoring --dry-run=client -o yaml | kubectl apply -f - 2>&1 | Out-Null

    Write-Host "    SRE Agent (Secret deja rempli avec le token)..." -ForegroundColor Yellow
    kind load docker-image sre-agent:latest --name sre-cluster 2>&1 | Out-Null
    kubectl apply -f "$PSScriptRoot\..\sre-agent-deploy.yaml" 2>&1 | Out-Null

    Write-Host "    Attente Grafana + SRE Agent (peut prendre 3 min)..." -ForegroundColor Yellow
    kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=grafana -n monitoring --timeout=300s 2>&1 | Out-Null
    kubectl wait --for=condition=Available deployment/sre-agent -n sre-agent --timeout=120s 2>&1 | Out-Null

    Write-Host "    Initialisation gitops-repo dans le pod SRE Agent..." -ForegroundColor Yellow
    $SRE_POD = kubectl get pod -n sre-agent -l app=sre-agent --no-headers `
        -o custom-columns="NAME:.metadata.name" 2>&1 | Select-Object -First 1
    if ($SRE_POD -and $SRE_POD -notmatch "Error") {
        kubectl exec -n sre-agent $SRE_POD -- sh -c `
            "git init /gitops-repo && git -C /gitops-repo config user.name SRE-Copilot && git -C /gitops-repo config user.email sre-copilot@local && mkdir -p /gitops-repo/incidents" `
            2>&1 | Out-Null
        Write-Host "    gitops-repo initialise." -ForegroundColor Green
    }

    # ── Kyverno + politiques (Mission 4) ─────────────────────────────────────
    Write-Host "    Kyverno..." -ForegroundColor Yellow
    helm repo add kyverno https://kyverno.github.io/kyverno/ 2>&1 | Out-Null
    helm repo update 2>&1 | Out-Null
    if (-not (helm list -n kyverno -q 2>&1 | Select-String "^kyverno$")) {
        helm install kyverno kyverno/kyverno -n kyverno --create-namespace --timeout 5m 2>&1 | Out-Null
        kubectl wait --for=condition=Ready pods --all -n kyverno --timeout=180s 2>&1 | Out-Null
    }
    kubectl apply -f "$PSScriptRoot\..\kyverno\policies\" 2>&1 | Out-Null
    Write-Host "    Kyverno OK (4 ClusterPolicies en mode Audit)." -ForegroundColor Green

    # ── Mission 5 : Dashboard Grafana auto-importe via sidecar ────────────────
    Write-Host "    Dashboard Grafana (Mission 5)..." -ForegroundColor Yellow
    kubectl create configmap sre-copilot-dashboard `
        --from-file=grafana-dashboard.json="$PSScriptRoot\..\monitoring\grafana-dashboard.json" `
        -n monitoring --dry-run=client -o yaml | kubectl apply -f - 2>&1 | Out-Null
    kubectl label configmap sre-copilot-dashboard -n monitoring grafana_dashboard=1 --overwrite 2>&1 | Out-Null
    Write-Host "    Dashboard Grafana 'SRE Copilot - KPIs' auto-importe." -ForegroundColor Green

    Write-Host "    Stack complete." -ForegroundColor Green
    Write-Host ""
}

# -------------------------------------------------------
# 2. Demarrer n8n Docker standalone
# -------------------------------------------------------
Write-Host "[2] Container n8n Docker..." -ForegroundColor Yellow
$n8nRunning = docker ps --filter "name=n8n" --filter "status=running" -q 2>&1
if (-not $n8nRunning) {
    docker start n8n 2>&1 | Out-Null
    Start-Sleep -Seconds 3
}
$n8nOk = docker ps --filter "name=n8n" --filter "status=running" -q 2>&1
if ($n8nOk) {
    Write-Host "    n8n OK -> http://localhost:5678" -ForegroundColor Green
} else {
    Write-Host "    ERREUR: n8n ne demarre pas" -ForegroundColor Red
}
Write-Host ""

# -------------------------------------------------------
# Helper: lancer un port-forward persistant (survit a la
# fermeture du terminal principal)
# -------------------------------------------------------
function Start-PersistentPF {
    param(
        [string]$Label,
        [string]$Resource,
        [string]$Namespace,
        [int]$LocalPort,
        [int]$RemotePort,
        [string]$HealthUrl = ""
    )
    # Liberer le port si occupe
    $existing = Get-NetTCPConnection -LocalPort $LocalPort -ErrorAction SilentlyContinue
    if ($existing) {
        $existing | Select-Object -ExpandProperty OwningProcess -Unique |
            ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 1
    }

    $address = if ($Label -eq "SRE Agent") { "--address 0.0.0.0" } else { "" }
    $cmd = "kubectl port-forward $address $Resource -n $Namespace ${LocalPort}:${RemotePort}"

    # WindowStyle Minimized = fenetre reduite mais independante du terminal appelant
    Start-Process powershell `
        -ArgumentList "-NoExit -Command $cmd" `
        -WindowStyle Minimized

    # Attendre que le port reponde (max 10s)
    $ready = $false
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 1
        $listening = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue
        if ($listening) { $ready = $true; break }
    }

    if ($ready) {
        Write-Host "    OK  $Label -> http://localhost:$LocalPort" -ForegroundColor Green
    } else {
        Write-Host "    ECHEC $Label (port $LocalPort)" -ForegroundColor Red
    }
}

# -------------------------------------------------------
# 3. Port-forwards persistants
# -------------------------------------------------------
Write-Host "[3] Demarrage des port-forwards persistants..." -ForegroundColor Yellow
Write-Host ""

Start-PersistentPF -Label "Grafana"      -Resource "svc/monitoring-grafana"                     -Namespace "monitoring" -LocalPort 3000 -RemotePort 80
Start-PersistentPF -Label "Prometheus"   -Resource "svc/monitoring-kube-prometheus-prometheus"   -Namespace "monitoring" -LocalPort 9090 -RemotePort 9090
Start-PersistentPF -Label "Alertmanager" -Resource "svc/monitoring-kube-prometheus-alertmanager" -Namespace "monitoring" -LocalPort 9093 -RemotePort 9093
Start-PersistentPF -Label "ArgoCD"       -Resource "svc/argocd-server"                          -Namespace "argocd"     -LocalPort 8080 -RemotePort 80
Start-PersistentPF -Label "SRE Agent"    -Resource "svc/sre-agent-service"                      -Namespace "sre-agent"  -LocalPort 8001 -RemotePort 8000
Write-Host ""

# -------------------------------------------------------
# 4. Health checks
# -------------------------------------------------------
Write-Host "[4] Health checks..." -ForegroundColor Yellow

function Test-Http {
    param([string]$Name, [string]$Url, [string]$Expected = "")
    try {
        $resp = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -ErrorAction Stop
        if ($Expected -and $resp.Content -notmatch $Expected) {
            Write-Host "    WARN $Name -> reponse inattendue" -ForegroundColor Yellow
        } else {
            Write-Host "    OK   $Name -> $Url" -ForegroundColor Green
        }
    } catch {
        Write-Host "    FAIL $Name -> $Url ($($_.Exception.Message))" -ForegroundColor Red
    }
}

Start-Sleep -Seconds 3
Test-Http -Name "SRE Agent  " -Url "http://localhost:8001/health"   -Expected "ok"
Test-Http -Name "Grafana    " -Url "http://localhost:3000/api/health"
Test-Http -Name "Prometheus " -Url "http://localhost:9090/-/healthy"
Test-Http -Name "Alertmanager" -Url "http://localhost:9093/-/healthy"
Test-Http -Name "n8n        " -Url "http://localhost:5678/healthz"

Write-Host ""

# -------------------------------------------------------
# 5. Ouvrir les navigateurs
# -------------------------------------------------------
Write-Host "[5] Ouverture des navigateurs..." -ForegroundColor Cyan
Start-Process "http://localhost:3000"
Start-Process "http://localhost:9090"
Start-Process "http://localhost:5678"
Start-Process "http://localhost:8080"

# -------------------------------------------------------
# Recapitulatif
# -------------------------------------------------------
Write-Host ""
Write-Host "===============================" -ForegroundColor Green
Write-Host "   ENVIRONNEMENT PRET !" -ForegroundColor Green
Write-Host "==============================="
Write-Host ""
Write-Host "  Grafana      -> http://localhost:3000  (admin / prom-operator)" -ForegroundColor White
Write-Host "  Prometheus   -> http://localhost:9090" -ForegroundColor White
Write-Host "  Alertmanager -> http://localhost:9093" -ForegroundColor White
Write-Host "  n8n          -> http://localhost:5678" -ForegroundColor White
Write-Host "  ArgoCD       -> http://localhost:8080  (admin / Sre@Copilot2026)" -ForegroundColor White
Write-Host "  SRE Agent    -> http://localhost:8001/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Alertmanager envoie UNIQUEMENT les alertes namespace=demo vers n8n" -ForegroundColor Cyan
Write-Host "  Deduplication active : meme alerte ignoree pendant 10 minutes" -ForegroundColor Cyan
Write-Host ""
Write-Host "  IMPORTANT: les fenetres PowerShell reduites = port-forwards actifs" -ForegroundColor Yellow
Write-Host "             Ne pas les fermer !" -ForegroundColor Yellow
