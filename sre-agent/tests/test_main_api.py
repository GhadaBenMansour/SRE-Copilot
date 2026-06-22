"""
Tests des endpoints FastAPI via TestClient (pas de vrai serveur HTTP).
"""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    return TestClient(main.app)


# ════════════════════════════════════════════════════════════════════════════
# /health — sonde liveness Kubernetes
# ════════════════════════════════════════════════════════════════════════════

class TestHealth:

    def test_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_returns_expected_payload(self, client):
        r = client.get("/health")
        assert r.json() == {"status": "ok", "service": "sre-copilot"}


# ════════════════════════════════════════════════════════════════════════════
# /api/stats — KPIs agreges
# ════════════════════════════════════════════════════════════════════════════

class TestApiStats:

    def test_empty_when_no_incidents(self, client, isolated_incidents_log):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["auto_remediated"] == 0
        assert data["success_rate"] == 0.0

    def test_aggregates_correctly_with_3_incidents(self, client, populated_incidents_log):
        r = client.get("/api/stats")
        data = r.json()
        assert data["total"] == 3
        assert data["auto_remediated"] == 2          # 2 sur 3 ont auto_remediation_applied=True
        assert data["argocd_synced"] == 1            # 1 seul a argocd_sync_triggered=True
        assert data["success_rate"] == pytest.approx(66.7, rel=0.01)

    def test_mttr_computed(self, client, populated_incidents_log):
        r = client.get("/api/stats")
        data = r.json()
        # MTTR = (180 + 220 + 150) / 3 = 183.33
        assert data["mttr_seconds"] == pytest.approx(183.33, rel=0.01)

    def test_classifications_grouped(self, client, populated_incidents_log):
        r = client.get("/api/stats")
        cls = r.json()["classifications"]
        assert cls["CrashLoopBackOff"] == 1
        assert cls["OOMKilled"]        == 1
        assert cls["Unknown"]          == 1


# ════════════════════════════════════════════════════════════════════════════
# /api/incidents — liste detaillee
# ════════════════════════════════════════════════════════════════════════════

class TestApiIncidents:

    def test_empty_when_no_log(self, client, isolated_incidents_log):
        r = client.get("/api/incidents")
        assert r.status_code == 200
        assert r.json()["count"] == 0
        assert r.json()["incidents"] == []

    def test_returns_all_incidents(self, client, populated_incidents_log):
        r = client.get("/api/incidents")
        data = r.json()
        assert data["count"] == 3
        assert len(data["incidents"]) == 3

    def test_respects_limit_parameter(self, client, populated_incidents_log):
        r = client.get("/api/incidents?limit=2")
        data = r.json()
        assert data["count"] == 3            # count = total persiste
        assert len(data["incidents"]) == 2   # mais on n'en retourne que 2


# ════════════════════════════════════════════════════════════════════════════
# /dashboard — page HTML
# ════════════════════════════════════════════════════════════════════════════

class TestDashboard:

    def test_returns_html(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")

    def test_html_contains_expected_markers(self, client):
        r = client.get("/dashboard")
        body = r.text
        # Doit etre une vraie page (pas juste vide)
        assert "<!DOCTYPE html>" in body or "<html" in body.lower()
        assert "SRE Copilot" in body


# ════════════════════════════════════════════════════════════════════════════
# /metrics — endpoint Prometheus
# ════════════════════════════════════════════════════════════════════════════

class TestMetrics:

    def test_returns_200(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_returns_prometheus_format(self, client):
        r = client.get("/metrics")
        # Content-Type Prometheus standard
        assert "text/plain" in r.headers["content-type"]
        # Le corps doit contenir au moins un compteur
        assert b"sre_" in r.content or b"# HELP" in r.content


# ════════════════════════════════════════════════════════════════════════════
# /alert — webhook Alertmanager
# ════════════════════════════════════════════════════════════════════════════

class TestAlertWebhook:

    def test_no_action_when_no_firing_alerts(self, client):
        """Alertes 'resolved' uniquement → l'agent ne fait rien."""
        payload = {
            "version": "4",
            "status":  "resolved",
            "alerts": [{
                "status": "resolved",
                "labels": {
                    "alertname": "PodRestartingTooMuch",
                    "namespace": "demo",
                    "pod":       "x",
                    "severity":  "critical",
                },
                "annotations": {"summary": "test"},
            }],
        }
        r = client.post("/alert", json=payload)
        assert r.status_code == 200
        assert "No firing alerts" in r.json()["message"]

    def test_rejects_invalid_payload(self, client):
        """Payload mal forme → 422 Unprocessable Entity."""
        r = client.post("/alert", json={"foo": "bar"})
        assert r.status_code == 422  # Pydantic validation error
