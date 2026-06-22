"""
Tests du module metrics.py (compteurs Prometheus).
"""
import pytest
import metrics


class TestRecordInvestigation:

    def test_increments_alerts_total(self, sample_agent_response_dict):
        """record_investigation doit incrementer sre_alerts_total avec les bons labels."""
        before = metrics.alerts_total.labels(
            classification="CrashLoopBackOff", severity="critical", namespace="demo"
        )._value.get()
        metrics.record_investigation(sample_agent_response_dict, fix_type="scale_to_zero")
        after = metrics.alerts_total.labels(
            classification="CrashLoopBackOff", severity="critical", namespace="demo"
        )._value.get()
        assert after == before + 1

    def test_increments_remediated_when_applied(self, sample_agent_response_dict):
        before = metrics.remediated_total.labels(
            classification="CrashLoopBackOff", fix_type="scale_to_zero", result="success"
        )._value.get()
        metrics.record_investigation(sample_agent_response_dict, fix_type="scale_to_zero")
        after = metrics.remediated_total.labels(
            classification="CrashLoopBackOff", fix_type="scale_to_zero", result="success"
        )._value.get()
        assert after == before + 1

    def test_no_crash_with_minimal_data(self):
        """record_investigation tolere les payloads incomplets (defaults Unknown/unknown)."""
        metrics.record_investigation({}, fix_type="none")
        # Ne doit pas lever d'exception


class TestRenderMetrics:

    def test_returns_bytes(self):
        data, content_type = metrics.render_metrics()
        assert isinstance(data, bytes)
        assert isinstance(content_type, str)

    def test_content_type_is_prometheus(self):
        _, content_type = metrics.render_metrics()
        # Standard Prometheus content-type
        assert "text/plain" in content_type or "application/openmetrics" in content_type

    def test_contains_sre_metrics(self):
        data, _ = metrics.render_metrics()
        text = data.decode("utf-8")
        # Au moins une de nos metriques doit apparaitre
        assert "sre_alerts_total" in text or "sre_agent_info" in text
