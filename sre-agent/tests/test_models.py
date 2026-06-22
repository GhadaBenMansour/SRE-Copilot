"""
Tests de validation des modeles Pydantic (models.py).
Objectif : garantir que tout payload mal forme est rejete proprement.
"""
import pytest
from pydantic import ValidationError

from models import Alert, AlertLabel, AlertAnnotation, AlertManagerPayload, AgentResponse, RemediationStep


class TestAlertLabel:

    def test_minimal_fields_ok(self):
        lbl = AlertLabel(alertname="X")
        assert lbl.alertname == "X"
        assert lbl.namespace == "default"   # default value
        assert lbl.severity  == "warning"   # default value

    def test_alertname_is_required(self):
        with pytest.raises(ValidationError):
            AlertLabel()  # missing alertname

    def test_accepts_optional_fields(self):
        lbl = AlertLabel(
            alertname="X", namespace="prod", pod="my-pod",
            deployment="my-deploy", severity="critical", container="app",
        )
        assert lbl.deployment == "my-deploy"


class TestAlert:

    def test_minimal_fields_ok(self, sample_alert_dict):
        alert = Alert(**sample_alert_dict)
        assert alert.status == "firing"
        assert alert.labels.alertname == "PodRestartingTooMuch"

    def test_status_is_required(self):
        with pytest.raises(ValidationError):
            Alert(labels={"alertname": "X"}, annotations={})


class TestAlertManagerPayload:

    def test_with_one_alert(self, sample_alert_dict):
        payload = AlertManagerPayload(status="firing", alerts=[sample_alert_dict])
        assert len(payload.alerts) == 1

    def test_rejects_missing_alerts_field(self):
        with pytest.raises(ValidationError):
            AlertManagerPayload(status="firing")


class TestRemediationStep:

    def test_valid_step(self):
        step = RemediationStep(order=1, action="Test", description="...")
        assert step.order == 1
        assert step.command is None  # optionnel

    def test_order_must_be_int(self):
        with pytest.raises(ValidationError):
            RemediationStep(order="not_an_int", action="X", description="Y")


class TestAgentResponse:

    def test_full_response(self, sample_agent_response_dict):
        # On retire les champs Pydantic-incompatibles si presents (le dict est riche)
        resp = AgentResponse(**sample_agent_response_dict)
        assert resp.classification == "CrashLoopBackOff"
        assert len(resp.runbook) == 3
        assert resp.auto_remediation_applied is True

    def test_minimal_response(self):
        resp = AgentResponse(
            alert_name="X", namespace="demo", severity="info",
            classification="Unknown", root_cause="...", runbook=[],
            auto_remediation_applied=False,
        )
        # Les champs optionnels gardent leurs defaults
        assert resp.git_pr_url is None
        assert resp.argocd_sync_triggered is False
        assert resp.investigation_log == []
