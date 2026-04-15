"""
ArgoCD tools for the SRE Agent.
Interacts with the ArgoCD API to sync applications and get their status.
"""
import os
import json
import logging
import subprocess
import requests
from langchain.tools import tool

logger = logging.getLogger(__name__)

ARGOCD_SERVER = os.getenv("ARGOCD_SERVER", "https://localhost:8080")
ARGOCD_TOKEN = os.getenv("ARGOCD_TOKEN", "")
ARGOCD_INSECURE = os.getenv("ARGOCD_INSECURE", "true").lower() == "true"


def _argocd_headers() -> dict:
    return {
        "Authorization": f"Bearer {ARGOCD_TOKEN}",
        "Content-Type": "application/json",
    }


def _argocd_get(path: str) -> tuple[bool, dict]:
    """Make a GET request to ArgoCD API."""
    try:
        resp = requests.get(
            f"{ARGOCD_SERVER}{path}",
            headers=_argocd_headers(),
            verify=not ARGOCD_INSECURE,
            timeout=15,
        )
        return resp.ok, resp.json()
    except Exception as e:
        return False, {"error": str(e)}


def _argocd_post(path: str, body: dict = None) -> tuple[bool, dict]:
    """Make a POST request to ArgoCD API."""
    try:
        resp = requests.post(
            f"{ARGOCD_SERVER}{path}",
            headers=_argocd_headers(),
            json=body or {},
            verify=not ARGOCD_INSECURE,
            timeout=30,
        )
        return resp.ok, resp.json()
    except Exception as e:
        return False, {"error": str(e)}


def _run_argocd_cli(args: list[str]) -> str:
    """Fallback: use argocd CLI if available."""
    try:
        cmd = ["argocd"] + args
        if ARGOCD_INSECURE:
            cmd += ["--insecure"]
        if ARGOCD_TOKEN:
            cmd += ["--auth-token", ARGOCD_TOKEN]
        cmd += ["--server", ARGOCD_SERVER.replace("https://", "").replace("http://", "")]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"ERROR: {e}"


@tool
def list_argocd_apps(input: str) -> str:
    """
    List all ArgoCD applications and their sync/health status.
    Input: ignored (pass any string like '.')
    """
    ok, data = _argocd_get("/api/v1/applications")
    if not ok:
        # Try CLI fallback
        return _run_argocd_cli(["app", "list"])

    apps = data.get("items", [])
    if not apps:
        return "No ArgoCD applications found."

    lines = ["NAME | SYNC | HEALTH | NAMESPACE"]
    for app in apps:
        name = app.get("metadata", {}).get("name", "?")
        sync = app.get("status", {}).get("sync", {}).get("status", "?")
        health = app.get("status", {}).get("health", {}).get("status", "?")
        ns = app.get("spec", {}).get("destination", {}).get("namespace", "?")
        lines.append(f"{name} | {sync} | {health} | {ns}")

    return "\n".join(lines)


@tool
def get_argocd_app_status(input: str) -> str:
    """
    Get detailed status of an ArgoCD application.
    Input: application name, e.g. 'demo-app'
    """
    app_name = input.strip()
    ok, data = _argocd_get(f"/api/v1/applications/{app_name}")
    if not ok:
        return _run_argocd_cli(["app", "get", app_name])

    status = data.get("status", {})
    sync = status.get("sync", {}).get("status", "?")
    health = status.get("health", {}).get("status", "?")
    message = status.get("operationState", {}).get("message", "")
    conditions = status.get("conditions", [])

    result = [
        f"App: {app_name}",
        f"Sync: {sync}",
        f"Health: {health}",
    ]
    if message:
        result.append(f"Message: {message}")
    if conditions:
        result.append("Conditions:")
        for c in conditions:
            result.append(f"  - {c.get('type')}: {c.get('message')}")

    return "\n".join(result)


@tool
def sync_argocd_app(input: str) -> str:
    """
    Trigger a sync for an ArgoCD application to deploy the latest GitOps changes.
    Input: application name, e.g. 'demo-app'
    """
    app_name = input.strip()
    ok, data = _argocd_post(f"/api/v1/applications/{app_name}/sync", {
        "prune": False,
        "dryRun": False,
    })
    if not ok:
        # Try CLI fallback
        return _run_argocd_cli(["app", "sync", app_name])

    phase = data.get("status", {}).get("operationState", {}).get("phase", "initiated")
    return f"Sync triggered for '{app_name}'. Phase: {phase}"


@tool
def rollback_argocd_app(input: str) -> str:
    """
    Rollback an ArgoCD application to the previous revision.
    Input format: 'app_name' or 'app_name/revision_id'
    Example: 'demo-app' or 'demo-app/3'
    """
    parts = input.strip().split("/")
    app_name = parts[0]
    revision = int(parts[1]) if len(parts) > 1 else 0  # 0 = previous

    ok, data = _argocd_post(f"/api/v1/applications/{app_name}/rollback", {
        "id": revision,
        "prune": False,
    })
    if not ok:
        return _run_argocd_cli(["app", "rollback", app_name])

    return f"Rollback initiated for '{app_name}'. Response: {json.dumps(data, indent=2)[:300]}"
