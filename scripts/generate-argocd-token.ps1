# generate-argocd-token.ps1
# Generates a PERMANENT (non-expiring) ArgoCD API token for the sre-copilot account
# and injects it directly into the sre-agent-secrets Kubernetes secret.
#
# Prerequisites:
#   - kubectl context = kind-sre-cluster
#   - ArgoCD port-forward active on localhost:8080 (HTTPS)
#   - ArgoCD admin password: Sre@Copilot2026
#
# Usage:
#   .\scripts\generate-argocd-token.ps1

param(
    [string]$ArgocdUrl      = "https://localhost:8080",
    [string]$AdminPassword  = "Sre@Copilot2026",
    [string]$AccountName    = "sre-copilot",
    [string]$TokenName      = "sre-copilot-permanent",
    [string]$Namespace      = "sre-agent",
    [string]$SecretName     = "sre-agent-secrets"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── 0. Ensure ArgoCD port-forward is active ────────────────────────────────────
$listening = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Write-Host "[*] Starting ArgoCD port-forward on :8080 ..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit -Command `"kubectl port-forward svc/argocd-server -n argocd 8080:443`"" -WindowStyle Minimized
    Start-Sleep -Seconds 8
}

# ── 1. Ensure sre-copilot account has apiKey capability ───────────────────────
Write-Host "[1] Patching argocd-cm — accounts.${AccountName}: apiKey" -ForegroundColor Cyan
kubectl patch configmap argocd-cm -n argocd --type merge `
    -p "{`"data`":{`"accounts.$AccountName`":`"apiKey`"}}" 2>&1 | Out-Null

# ── 2. Ensure RBAC: sre-copilot can sync apps ─────────────────────────────────
Write-Host "[2] Patching argocd-rbac-cm — sync policy" -ForegroundColor Cyan
$policy = "p, $AccountName, applications, get, */*, allow`np, $AccountName, applications, sync, */*, allow`np, $AccountName, applications, update, */*, allow`n"
kubectl patch configmap argocd-rbac-cm -n argocd --type merge `
    -p "{`"data`":{`"policy.csv`":`"$policy`",`"policy.default`":`"role:readonly`"}}" 2>&1 | Out-Null

# ── 3. Obtain admin JWT (short-lived session token just for creating API key) ──
Write-Host "[3] Authenticating as admin ..." -ForegroundColor Cyan
$authBody = "{`"username`":`"admin`",`"password`":`"$AdminPassword`"}"
$authResp  = Invoke-WebRequest -Uri "$ArgocdUrl/api/v1/session" -Method POST `
    -Body $authBody -ContentType "application/json" -SkipCertificateCheck
$adminToken = ($authResp.Content | ConvertFrom-Json).token

# ── 4. Generate permanent token (expiresIn=0 → no exp claim in JWT) ───────────
Write-Host "[4] Generating permanent API token for '$AccountName' ..." -ForegroundColor Cyan
$tokenBody = "{`"expiresIn`":0,`"name`":`"$TokenName`"}"
$headers   = @{ Authorization = "Bearer $adminToken" }
$tokenResp = Invoke-WebRequest -Uri "$ArgocdUrl/api/v1/account/$AccountName/token" `
    -Method POST -Body $tokenBody -ContentType "application/json" `
    -Headers $headers -SkipCertificateCheck
$permanentToken = ($tokenResp.Content | ConvertFrom-Json).token

# Verify no expiry in JWT payload
$payloadB64 = $permanentToken.Split('.')[1]
$padded     = $payloadB64 + '=' * ((4 - $payloadB64.Length % 4) % 4)
$payload    = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($padded)) | ConvertFrom-Json
if ($payload.PSObject.Properties['exp']) {
    Write-Warning "Token has an expiry: $($payload.exp). Something went wrong."
} else {
    Write-Host "    Token verified: NO exp claim — permanent." -ForegroundColor Green
}

# ── 5. Read existing secret values to preserve them ───────────────────────────
Write-Host "[5] Updating $SecretName in namespace $Namespace ..." -ForegroundColor Cyan
$decode = { param($b64) if ($b64) { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64)) } else { "" } }
$existing    = kubectl get secret $SecretName -n $Namespace -o json | ConvertFrom-Json
$githubToken = & $decode ($existing.data.GITHUB_TOKEN)
$gitName     = & $decode ($existing.data.GIT_USER_NAME)
$gitEmail    = & $decode ($existing.data.GIT_USER_EMAIL)

kubectl create secret generic $SecretName -n $Namespace `
    --from-literal=GITHUB_TOKEN="$githubToken" `
    --from-literal=ARGOCD_TOKEN="$permanentToken" `
    --from-literal=GIT_USER_NAME="$gitName" `
    --from-literal=GIT_USER_EMAIL="$gitEmail" `
    --dry-run=client -o yaml | kubectl apply -f - 2>&1 | Out-Null

# ── 6. Restart SRE Agent to pick up new token ─────────────────────────────────
Write-Host "[6] Restarting SRE Agent deployment ..." -ForegroundColor Cyan
kubectl rollout restart deployment/sre-agent -n $Namespace 2>&1 | Out-Null
kubectl rollout status deployment/sre-agent -n $Namespace --timeout=60s 2>&1 | Out-Null

Write-Host ""
Write-Host "Done! Permanent ArgoCD token injected and SRE Agent restarted." -ForegroundColor Green
Write-Host "Token sub: $($payload.sub)"
