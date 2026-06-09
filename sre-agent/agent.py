"""
SRE Copilot Agent — Three-phase investigation and GitOps remediation pipeline.

Phase 1 — Data Collection (Python, deterministic):
    Direct kubectl calls to collect pod status, logs, events.
    Always runs, no LLM dependency.

Phase 2 — Root Cause Analysis (Ollama JSON mode, single LLM call):
    Mistral classifies the incident, generates a runbook, and proposes a fix type.
    format="json" guarantees parseable output. Keyword fallback on LLM failure.

Phase 3 — GitOps Remediation (Python, only when AUTO_REMEDIATE=true):
    Applies the immediate fix (scale/restart), documents it via git commit,
    and triggers ArgoCD sync. Demonstrates the full GitOps loop:
    Alert → Investigate → Fix → Git commit → ArgoCD deploy.

Tool stack (open-source):
    Ollama/Mistral 7B  instead of  Azure OpenAI
    KinD + kubectl     instead of  AKS
    Local gitops-repo  instead of  GitHub (GITHUB_TOKEN optional for remote push)
    ArgoCD API         unchanged
"""
import asyncio
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from functools import partial

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from tools.kubectl_tools import _run_kubectl, resolve_pod_name, scale_deployment, restart_deployment
from tools.git_tools import create_fix_pr
from tools.argocd_tools import sync_argocd_app
from models import Alert, AgentResponse, RemediationStep
import metrics

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL",  "http://host.docker.internal:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL",     "mistral")
AUTO_REMEDIATE   = os.getenv("AUTO_REMEDIATE",   "false").lower() == "true"
GITOPS_REPO_PATH = os.getenv("GITOPS_REPO_PATH", "/gitops-repo")
ARGOCD_APP_NAME  = os.getenv("ARGOCD_APP_NAME",  "demo-app")  # ArgoCD app to sync after fix
INCIDENTS_LOG    = os.path.join(GITOPS_REPO_PATH, "incidents", "responses.jsonl")

# Whitelist of accepted classifications (rejects LLM hallucinations like 'PolicyViolation')
ALLOWED_CLASSIFICATIONS = {
    "CrashLoopBackOff", "OOMKilled", "ImagePullBackOff",
    "ConfigError", "ResourceExhausted", "NetworkError", "Unknown",
}

# ArgoCD sync makes sense only for fix types that REFRESH the deployment.
# scale_to_zero must NOT trigger sync — it would re-create the pod from Git and
# undo the remediation, causing an infinite loop.
ARGOCD_SYNC_AFTER_FIX = {"restart"}


def _persist_response(response_dict: dict) -> None:
    """Append the investigation response as a JSON line to the incidents log."""
    try:
        os.makedirs(os.path.dirname(INCIDENTS_LOG), exist_ok=True)
        with open(INCIDENTS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(response_dict, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning(f"Could not persist response: {exc}")

# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a senior SRE engineer specializing in Kubernetes incident response. "
    "Analyze the alert and investigation data provided. "
    "Respond ONLY with a valid JSON object — no explanation, no markdown, no text outside the JSON. "
    "CRITICAL: the 'classification' field MUST be EXACTLY one of the 7 values listed in the prompt. "
    "Do NOT invent new classes (e.g. 'PolicyViolation', 'DeploymentError', etc.). "
    "If the issue is a policy/config problem, use 'ConfigError'. If unsure, use 'Unknown'."
)

_PROMPT = """\
ALERT:
{alert_context}

INVESTIGATION DATA:
{investigation_data}

Based on this data, classify the incident, generate a runbook, and propose a fix.
Respond with ONLY this JSON (all fields required):
{{
  "classification": "<one of: CrashLoopBackOff | OOMKilled | ImagePullBackOff | ConfigError | ResourceExhausted | NetworkError | Unknown>",
  "root_cause": "<technical explanation of why this alert fired, referencing the data above>",
  "runbook": [
    {{"order": 1, "action": "<name>", "command": "<exact kubectl command>", "description": "<what and why>"}},
    {{"order": 2, "action": "<name>", "command": "<exact kubectl command>", "description": "<what and why>"}},
    {{"order": 3, "action": "<name>", "command": "<exact kubectl command>", "description": "<what and why>"}}
  ],
  "proposed_fix": {{
    "applicable": true,
    "type": "<one of: scale_to_zero | restart | none>",
    "description": "<human-readable description of what the automated fix will do>"
  }},
  "auto_remediation_applied": false,
  "remediation_details": null,
  "git_pr_url": null,
  "argocd_sync_triggered": false
}}

Fix type guide:
- "scale_to_zero": use for CrashLoopBackOff (stops the crash loop immediately, safe for demo)
- "restart": use for transient failures (OOMKilled, ConfigError) where a fresh start may help
- "none": use when fix cannot be automated (ImagePullBackOff, NetworkError, Unknown)"""


# ── Phase 1: Deterministic kubectl data collection ─────────────────────────────

def _collect_kubectl_data(namespace: str, pod: str) -> dict[str, str]:
    """
    Collect all investigation data directly via kubectl (no LLM involvement).
    Uses ServiceAccount token in-cluster; falls back to local kubeconfig.
    """
    data: dict[str, str] = {}

    data["pod_status"] = _run_kubectl(["get", "pods", "-n", namespace, "-o", "wide"])

    if pod and pod != "unknown":
        full_pod = resolve_pod_name(namespace, pod)

        # Previous container logs capture the crash reason
        logs = _run_kubectl(["logs", full_pod, "-n", namespace, "--tail=50", "--previous"])
        if "ERROR" in logs or not logs.strip() or logs == "(empty output)":
            logs = _run_kubectl(["logs", full_pod, "-n", namespace, "--tail=50"])
        data["pod_logs"] = logs

        data["pod_describe"] = _run_kubectl(["describe", "pod", full_pod, "-n", namespace])

    data["namespace_events"] = _run_kubectl([
        "get", "events", "-n", namespace,
        "--sort-by=.lastTimestamp",
        "--field-selector=type!=Normal",
    ])

    return data


def _format_investigation(data: dict[str, str]) -> str:
    labels = {
        "pod_status":       "POD STATUS",
        "pod_logs":         "POD LOGS (last 50 lines of previous container)",
        "pod_describe":     "POD DESCRIBE (events + conditions)",
        "namespace_events": "NAMESPACE EVENTS (warnings only)",
    }
    sections = []
    for key, label in labels.items():
        content = data.get(key, "").strip()
        if content and content != "(empty output)":
            sections.append(f"=== {label} ===\n{content[:2000]}")
    return "\n\n".join(sections) if sections else "No kubectl data available."


# ── Phase 2: LLM root cause analysis (JSON mode) ──────────────────────────────

def _keyword_fallback(data: dict[str, str]) -> dict:
    """
    Rule-based fallback when LLM is unavailable or returns invalid JSON.
    Classifies based on actual kubectl output from Phase 1.
    """
    text = " ".join(data.values()).lower()

    if "crashloopbackoff" in text:
        return {
            "classification": "CrashLoopBackOff",
            "root_cause": "Container crashes immediately after start (exit code != 0). Kubernetes restarts it in exponential-backoff loop.",
            "runbook": [
                {"order": 1, "action": "Check previous logs",   "command": "kubectl logs <pod> -n <ns> --previous", "description": "Find crash reason in last container run."},
                {"order": 2, "action": "Describe pod",          "command": "kubectl describe pod <pod> -n <ns>",    "description": "Review exit codes, restart count, events."},
                {"order": 3, "action": "Fix or scale to zero",  "command": "kubectl scale deployment <deploy> --replicas=0 -n <ns>", "description": "Stop crash loop while root cause is fixed."},
            ],
            "proposed_fix": {"applicable": True, "type": "scale_to_zero", "description": "Scale deployment to 0 replicas to stop the crash loop."},
            "auto_remediation_applied": False, "remediation_details": None, "git_pr_url": None, "argocd_sync_triggered": False,
        }
    if "oomkilled" in text or "out of memory" in text:
        return {
            "classification": "OOMKilled",
            "root_cause": "Container killed by kernel OOM killer — memory limit too low.",
            "runbook": [
                {"order": 1, "action": "Check memory usage", "command": "kubectl top pods -n <ns>",                                                    "description": "Confirm current memory consumption."},
                {"order": 2, "action": "Increase limit",     "command": "kubectl set resources deployment/<d> --limits=memory=512Mi -n <ns>",          "description": "Raise memory limit."},
                {"order": 3, "action": "Restart pod",        "command": "kubectl rollout restart deployment/<deploy> -n <ns>",                         "description": "Apply new limits with a rolling restart."},
            ],
            "proposed_fix": {"applicable": True, "type": "restart", "description": "Rollout restart to apply new resource limits."},
            "auto_remediation_applied": False, "remediation_details": None, "git_pr_url": None, "argocd_sync_triggered": False,
        }
    if "imagepullbackoff" in text or "errimagepull" in text:
        return {
            "classification": "ImagePullBackOff",
            "root_cause": "Kubernetes cannot pull the container image.",
            "runbook": [
                {"order": 1, "action": "Inspect pull error",    "command": "kubectl describe pod <pod> -n <ns>", "description": "Find exact pull error in Events."},
                {"order": 2, "action": "Verify image exists",   "command": "docker pull <image>:<tag>",          "description": "Confirm image and tag exist in registry."},
                {"order": 3, "action": "Check imagePullSecret", "command": "kubectl get secret -n <ns>",         "description": "Verify registry credentials are configured."},
            ],
            "proposed_fix": {"applicable": False, "type": "none", "description": "Cannot auto-fix — requires manual image correction."},
            "auto_remediation_applied": False, "remediation_details": None, "git_pr_url": None, "argocd_sync_triggered": False,
        }
    return {
        "classification": "Unknown",
        "root_cause": "Root cause undetermined. Manual investigation required.",
        "runbook": [
            {"order": 1, "action": "Investigate pod",  "command": "kubectl describe pod <pod> -n <ns>", "description": "Review all events and conditions."},
            {"order": 2, "action": "Check logs",        "command": "kubectl logs <pod> -n <ns>",         "description": "Review application output."},
        ],
        "proposed_fix": {"applicable": False, "type": "none", "description": "No automated fix available."},
        "auto_remediation_applied": False, "remediation_details": None, "git_pr_url": None, "argocd_sync_triggered": False,
    }


def _llm_analyze_sync(alert_context: str, investigation_data: dict[str, str]) -> dict:
    """
    Single LLM call with Ollama JSON output mode.
    format="json" constrains Ollama to produce valid JSON (not just any text).
    """
    llm = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        temperature=0,
        format="json",
        num_predict=1024,
    )

    prompt = _PROMPT.format(
        alert_context=alert_context,
        investigation_data=_format_investigation(investigation_data),
    )

    response = llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])

    raw = response.content.strip()
    logger.debug(f"LLM raw ({len(raw)} chars): {raw[:300]}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"LLM returned non-JSON: {raw[:200]}")


# ── Phase 3: GitOps remediation ───────────────────────────────────────────────

def _ensure_gitops_repo() -> bool:
    """Initialize the gitops-repo as a git repository if not already done."""
    git_dir = os.path.join(GITOPS_REPO_PATH, ".git")
    if os.path.exists(git_dir):
        return True
    if not os.path.exists(GITOPS_REPO_PATH):
        os.makedirs(GITOPS_REPO_PATH, exist_ok=True)
    for cmd in [
        ["git", "init",          GITOPS_REPO_PATH],
        ["git", "-C", GITOPS_REPO_PATH, "config", "user.name",  "SRE-Copilot"],
        ["git", "-C", GITOPS_REPO_PATH, "config", "user.email", "sre-copilot@local"],
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            logger.error(f"git init step failed: {r.stderr}")
            return False
    logger.info(f"gitops-repo initialized at {GITOPS_REPO_PATH}")
    return True


def _derive_deployment_name(pod: str) -> str:
    """
    Derive deployment name from pod name.
    Pod names follow the pattern: <deployment>-<replicaset-hash>-<pod-hash>
    Example: crash-app-6d9dcddc79-zfkl9 → crash-app
    """
    parts = pod.rsplit("-", 2)
    return parts[0] if len(parts) == 3 else pod


def _apply_gitops_remediation_sync(
    alert: Alert,
    classification: str,
    fix_type: str,
) -> dict:
    """
    Phase 3: Full GitOps remediation loop.

    1. Immediate action  — scale to 0 or rollout restart (stops the symptom now)
    2. Git documentation — commit the incident state and action to gitops-repo
    3. ArgoCD sync       — trigger redeployment from git state

    This implements the PR→ArgoCD GitOps loop from the PFE spec.
    Without GITHUB_TOKEN: local git branch only (no remote push).
    With GITHUB_TOKEN: push + PR URL returned.
    """
    namespace   = alert.labels.namespace or "demo"
    pod         = alert.labels.pod or "unknown"
    deploy_name = _derive_deployment_name(resolve_pod_name(namespace, pod))
    timestamp   = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch      = f"fix/{deploy_name}-{classification.lower().replace(' ', '-')}-{timestamp}"

    result = {
        "auto_remediation_applied": False,
        "remediation_details":      None,
        "git_pr_url":               None,
        "argocd_sync_triggered":    False,
    }

    # ── 1. Immediate remediation action ───────────────────────────────────────
    logger.info(f"[Phase 3] Applying fix_type={fix_type} on {namespace}/{deploy_name}")

    if fix_type == "scale_to_zero":
        action_out = scale_deployment(namespace, deploy_name, 0)
        result["auto_remediation_applied"] = "ERROR" not in action_out
        result["remediation_details"] = f"Scaled {namespace}/{deploy_name} to 0 replicas to stop crash loop. Output: {action_out}"

    elif fix_type == "restart":
        action_out = restart_deployment(namespace, deploy_name)
        result["auto_remediation_applied"] = "ERROR" not in action_out
        result["remediation_details"] = f"Rollout restart on {namespace}/{deploy_name}. Output: {action_out}"

    # ── 2. Git commit: document incident + action in gitops-repo ──────────────
    if _ensure_gitops_repo():
        # Snapshot the current deployment YAML for audit trail
        current_yaml = _run_kubectl(["get", "deployment", deploy_name, "-n", namespace, "-o", "yaml"])

        incident_doc = (
            f"# SRE Copilot — Auto-remediation Record\n"
            f"# ========================================\n"
            f"# Timestamp:      {timestamp}\n"
            f"# Alert:          {alert.labels.alertname}\n"
            f"# Namespace:      {namespace}\n"
            f"# Deployment:     {deploy_name}\n"
            f"# Classification: {classification}\n"
            f"# Fix applied:    {fix_type}\n"
            f"# Remediated:     {result['auto_remediation_applied']}\n"
            f"# ========================================\n\n"
            f"# Deployment state at time of remediation:\n"
            f"{current_yaml}\n"
        )

        pr_payload = json.dumps({
            "branch":         branch,
            "file_path":      f"incidents/{namespace}/{deploy_name}-{timestamp}.yaml",
            "file_content":   incident_doc,
            "commit_message": (
                f"fix({namespace}): auto-remediate {classification} on {deploy_name}\n\n"
                f"Alert: {alert.labels.alertname}\n"
                f"Action: {fix_type}\n"
                f"Remediated: {result['auto_remediation_applied']}\n"
                f"Timestamp: {timestamp}"
            ),
            "pr_title": f"fix({namespace}): {classification} auto-remediation — {deploy_name}",
        })

        pr_result = create_fix_pr.func(pr_payload)
        logger.info(f"[Phase 3] Git result: {pr_result}")

        if "SUCCESS" in pr_result:
            result["git_pr_url"] = (
                pr_result.split("Open PR: ")[1].strip()
                if "Open PR: " in pr_result
                else f"local:branch/{branch}"
            )

    # ── 3. ArgoCD sync: only for fix types that need a refresh ────────────────
    # CRITICAL: scale_to_zero must NEVER trigger sync, otherwise ArgoCD would
    # re-apply replicas=1 from Git and undo our remediation → infinite loop.
    if fix_type in ARGOCD_SYNC_AFTER_FIX:
        try:
            sync_out = sync_argocd_app.func(ARGOCD_APP_NAME)
            if "ERROR" not in sync_out and "error" not in sync_out.lower():
                result["argocd_sync_triggered"] = True
                logger.info(f"[Phase 3] ArgoCD sync triggered: {sync_out}")
            else:
                logger.warning(f"[Phase 3] ArgoCD sync failed: {sync_out}")
        except Exception as exc:
            logger.warning(f"[Phase 3] ArgoCD sync failed (non-critical): {exc}")
    else:
        logger.info(f"[Phase 3] ArgoCD sync skipped — fix_type='{fix_type}' is terminal "
                    f"(syncing would undo the remediation)")

    return result


# ── Main entry point ───────────────────────────────────────────────────────────

async def run_sre_investigation(alert: Alert) -> AgentResponse:
    """
    Three-phase SRE investigation and GitOps remediation pipeline.

    Phase 1 — kubectl data collection   (always runs)
    Phase 2 — LLM classification + fix  (JSON mode, keyword fallback)
    Phase 3 — GitOps remediation        (only when AUTO_REMEDIATE=true)
    """
    namespace = alert.labels.namespace or "demo"
    pod       = alert.labels.pod or "unknown"
    start_ts  = time.monotonic()

    alert_context = (
        f"Alert:       {alert.labels.alertname}\n"
        f"Severity:    {alert.labels.severity}\n"
        f"Namespace:   {namespace}\n"
        f"Pod:         {pod}\n"
        f"Summary:     {alert.annotations.summary}\n"
        f"Description: {alert.annotations.description}\n"
        f"Started:     {alert.startsAt or 'unknown'}"
    )

    investigation_log: list[str] = []
    loop = asyncio.get_event_loop()

    # ── Phase 1: kubectl data collection ──────────────────────────────────────
    logger.info(f"[Phase 1] kubectl collection — {namespace}/{pod}")
    try:
        investigation_data: dict[str, str] = await loop.run_in_executor(
            None, partial(_collect_kubectl_data, namespace, pod)
        )
        for section, content in investigation_data.items():
            investigation_log.append(f"[kubectl:{section}] {content[:250].replace(chr(10), ' ')}")
        logger.info(f"[Phase 1] Collected {len(investigation_data)} sections")
    except Exception as exc:
        logger.error(f"[Phase 1] Failed: {exc}")
        investigation_data = {}
        investigation_log.append(f"[kubectl:ERROR] {exc}")

    # ── Phase 2: LLM analysis (JSON mode) ─────────────────────────────────────
    logger.info("[Phase 2] LLM JSON-mode analysis")
    try:
        parsed = await loop.run_in_executor(
            None, partial(_llm_analyze_sync, alert_context, investigation_data)
        )
        logger.info(f"[Phase 2] Classification: {parsed.get('classification')} | Fix: {parsed.get('proposed_fix', {}).get('type')}")
    except Exception as exc:
        logger.warning(f"[Phase 2] LLM failed ({exc}). Using keyword fallback.")
        metrics.llm_fallback_total.labels(reason="llm_error").inc()
        parsed = _keyword_fallback(investigation_data)
        investigation_log.append(f"[llm:fallback] {parsed['classification']}")

    # Validator: reject LLM hallucinations (e.g. 'PolicyViolation' not in allowed set)
    cls = parsed.get("classification", "Unknown")
    if cls not in ALLOWED_CLASSIFICATIONS:
        logger.warning(f"[Phase 2] LLM returned non-standard classification '{cls}' — "
                       f"normalizing via keyword fallback")
        metrics.llm_fallback_total.labels(reason="invalid_classification").inc()
        investigation_log.append(f"[validator] '{cls}' rejected (not in allowed set)")
        normalized = _keyword_fallback(investigation_data)
        # Keep the LLM's runbook + root_cause (they're often useful even if classif is off)
        # but override classification + proposed_fix with the safe fallback
        parsed["classification"] = normalized["classification"]
        parsed["proposed_fix"]   = normalized["proposed_fix"]
        investigation_log.append(f"[validator] normalized to '{normalized['classification']}'")

    # ── Phase 3: GitOps remediation ───────────────────────────────────────────
    proposed_fix = parsed.get("proposed_fix", {})
    fix_type     = proposed_fix.get("type", "none")

    if AUTO_REMEDIATE and proposed_fix.get("applicable") and fix_type != "none":
        logger.info(f"[Phase 3] AUTO_REMEDIATE=true — applying fix_type={fix_type}")
        investigation_log.append(f"[remediation] Starting: fix_type={fix_type}")
        try:
            remediation = await loop.run_in_executor(
                None,
                partial(_apply_gitops_remediation_sync, alert, parsed.get("classification", "Unknown"), fix_type),
            )
            parsed.update(remediation)
            investigation_log.append(
                f"[remediation] Done: auto_remediated={remediation.get('auto_remediation_applied')} "
                f"git={remediation.get('git_pr_url')} "
                f"argocd={remediation.get('argocd_sync_triggered')}"
            )
            logger.info(f"[Phase 3] Complete: {remediation}")
        except Exception as exc:
            logger.error(f"[Phase 3] Remediation failed: {exc}")
            investigation_log.append(f"[remediation:ERROR] {exc}")
    else:
        reason = (
            "AUTO_REMEDIATE=false (set env var to enable)"
            if not AUTO_REMEDIATE
            else f"fix not applicable (type={fix_type})"
        )
        logger.info(f"[Phase 3] Skipped — {reason}")
        investigation_log.append(f"[remediation:skipped] {reason}")

    # ── Build response ─────────────────────────────────────────────────────────
    runbook = [
        RemediationStep(**step) if isinstance(step, dict) else step
        for step in parsed.get("runbook", [])
    ] or [
        RemediationStep(
            order=1,
            action="Manual Investigation Required",
            description="No structured runbook generated. Review investigation_log for kubectl data.",
        )
    ]

    response = AgentResponse(
        alert_name=alert.labels.alertname,
        namespace=namespace,
        severity=alert.labels.severity or "unknown",
        classification=parsed.get("classification", "Unknown"),
        root_cause=parsed.get("root_cause", "Undetermined"),
        runbook=runbook,
        auto_remediation_applied=parsed.get("auto_remediation_applied", False),
        remediation_details=parsed.get("remediation_details"),
        git_pr_url=parsed.get("git_pr_url"),
        argocd_sync_triggered=parsed.get("argocd_sync_triggered", False),
        investigation_log=investigation_log,
        timestamp=datetime.now(timezone.utc).isoformat(),
        duration_seconds=round(time.monotonic() - start_ts, 2),
        pod=pod,
    )

    response_dict = response.model_dump()
    _persist_response(response_dict)

    # Record Prometheus metrics for this investigation
    try:
        metrics.record_investigation(response_dict, fix_type=fix_type)
    except Exception as exc:
        logger.warning(f"Could not record metrics: {exc}")

    return response
