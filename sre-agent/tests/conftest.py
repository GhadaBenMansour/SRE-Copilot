"""
Fixtures pytest partagees entre tous les tests.
Conventions :
  - Aucun test ne doit appeler le vrai cluster Kubernetes
  - Aucun test ne doit appeler le vrai Ollama
  - Tous les chemins disque utilisent tmp_path (sandbox)
"""
import os
import sys
import json
from pathlib import Path

import pytest

# ── Ajoute le dossier sre-agent/ au PYTHONPATH pour permettre `from agent import ...` ──
SRE_AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRE_AGENT_DIR))


# ── Fixtures de donnees realistes ─────────────────────────────────────────────

@pytest.fixture
def sample_crashloop_data():
    """Donnees kubectl typiques d'un pod en CrashLoopBackOff."""
    return {
        "pod_status": (
            "NAME                         READY   STATUS             RESTARTS\n"
            "crash-app-xxx-yyy            0/1     CrashLoopBackOff   8"
        ),
        "pod_logs": "Error: container exited with code 1\nFatal: exit",
        "pod_describe": "State: Waiting\n  Reason: CrashLoopBackOff",
        "namespace_events": "Warning  BackOff  Back-off restarting failed container",
    }


@pytest.fixture
def sample_oom_data():
    return {
        "pod_status": "myapp-xxx   0/1   OOMKilled   2",
        "pod_logs":   "Out of memory: Killed process 1",
        "pod_describe":   "State: Terminated\n  Reason: OOMKilled",
        "namespace_events": "Warning  OOMKilling  Memory cgroup out of memory",
    }


@pytest.fixture
def sample_imagepull_data():
    return {
        "pod_status": "myapp-xxx   0/1   ImagePullBackOff   0",
        "pod_logs":   "(empty output)",
        "pod_describe": "Failed to pull image: ImagePullBackOff",
        "namespace_events": "Warning Failed errimagepull",
    }


@pytest.fixture
def sample_unknown_data():
    return {
        "pod_status": "myapp-xxx   1/1   Running   0",
        "pod_logs":   "Just normal logs without any error",
        "pod_describe": "State: Running\n  Started: now",
        "namespace_events": "(no events)",
    }


@pytest.fixture
def sample_alert_dict():
    """Payload Alertmanager typique."""
    return {
        "status": "firing",
        "labels": {
            "alertname": "PodRestartingTooMuch",
            "namespace": "demo",
            "pod":       "crash-app",
            "severity":  "critical",
        },
        "annotations": {
            "summary":     "Pod restarting frequently",
            "description": "crash-app is restarting too often",
        },
    }


@pytest.fixture
def sample_agent_response_dict():
    """Reponse type de l'agent (apres une investigation reussie)."""
    return {
        "alert_name":                "PodRestartingTooMuch",
        "namespace":                 "demo",
        "severity":                  "critical",
        "classification":            "CrashLoopBackOff",
        "root_cause":                "Container exits with code 1",
        "runbook": [
            {"order": 1, "action": "Check logs",   "command": "kubectl logs ...", "description": "..."},
            {"order": 2, "action": "Describe pod", "command": "kubectl describe", "description": "..."},
            {"order": 3, "action": "Scale to 0",   "command": "kubectl scale ...","description": "..."},
        ],
        "auto_remediation_applied": True,
        "remediation_details":      "Scaled to 0",
        "git_pr_url":               "local:branch/fix/abc",
        "argocd_sync_triggered":    False,
        "investigation_log":        ["[Phase 1] OK", "[Phase 3] Complete"],
        "timestamp":                "2026-06-15T10:00:00",
        "duration_seconds":         180.5,
        "pod":                      "crash-app-xxx-yyy",
    }


# ── Fixture pour isoler les ecritures disque ──────────────────────────────────

@pytest.fixture
def isolated_incidents_log(tmp_path, monkeypatch):
    """
    Redirige INCIDENTS_LOG vers un fichier temporaire pour les tests.
    Garantit qu'aucun test ne pollue /gitops-repo/incidents/responses.jsonl.
    """
    log_file = tmp_path / "responses.jsonl"

    # Patch dans agent.py
    import agent
    monkeypatch.setattr(agent, "INCIDENTS_LOG", str(log_file))

    # Patch dans main.py (qui le lit aussi)
    import main
    monkeypatch.setattr(main, "INCIDENTS_LOG", str(log_file))

    return log_file


@pytest.fixture
def populated_incidents_log(isolated_incidents_log, sample_agent_response_dict):
    """Fichier JSONL avec 3 incidents pre-enregistres pour tester /api/stats."""
    incidents = [
        {**sample_agent_response_dict, "classification": "CrashLoopBackOff",
         "auto_remediation_applied": True,  "argocd_sync_triggered": False, "duration_seconds": 180},
        {**sample_agent_response_dict, "classification": "OOMKilled",
         "auto_remediation_applied": True,  "argocd_sync_triggered": True,  "duration_seconds": 220},
        {**sample_agent_response_dict, "classification": "Unknown",
         "auto_remediation_applied": False, "argocd_sync_triggered": False, "duration_seconds": 150},
    ]
    with open(isolated_incidents_log, "w") as f:
        for i in incidents:
            f.write(json.dumps(i) + "\n")
    return isolated_incidents_log
