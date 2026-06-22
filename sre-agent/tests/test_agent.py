"""
Tests de la logique critique de agent.py.

Focus :
  - _keyword_fallback : decision deterministe sans LLM
  - _derive_deployment_name : extraction du deployment a partir du nom de pod
  - _format_investigation : filtrage des sections vides
  - Constantes critiques : ALLOWED_CLASSIFICATIONS, ARGOCD_SYNC_AFTER_FIX
"""
import pytest
import agent


# ════════════════════════════════════════════════════════════════════════════
# _keyword_fallback : robustesse quand le LLM echoue
# ════════════════════════════════════════════════════════════════════════════

class TestKeywordFallback:

    def test_detects_crashloopbackoff(self, sample_crashloop_data):
        result = agent._keyword_fallback(sample_crashloop_data)
        assert result["classification"] == "CrashLoopBackOff"
        assert result["proposed_fix"]["applicable"] is True
        assert result["proposed_fix"]["type"] == "scale_to_zero"

    def test_detects_oomkilled(self, sample_oom_data):
        result = agent._keyword_fallback(sample_oom_data)
        assert result["classification"] == "OOMKilled"
        assert result["proposed_fix"]["type"] == "restart"

    def test_detects_imagepullbackoff(self, sample_imagepull_data):
        result = agent._keyword_fallback(sample_imagepull_data)
        assert result["classification"] == "ImagePullBackOff"
        # ImagePullBackOff necessite intervention humaine
        assert result["proposed_fix"]["applicable"] is False
        assert result["proposed_fix"]["type"] == "none"

    def test_unknown_when_no_match(self, sample_unknown_data):
        result = agent._keyword_fallback(sample_unknown_data)
        assert result["classification"] == "Unknown"
        assert result["proposed_fix"]["applicable"] is False

    def test_returns_required_fields(self, sample_crashloop_data):
        """Le format de sortie doit etre coherent avec ce que la Phase 3 attend."""
        result = agent._keyword_fallback(sample_crashloop_data)
        required_keys = {
            "classification", "root_cause", "runbook", "proposed_fix",
            "auto_remediation_applied", "remediation_details",
            "git_pr_url", "argocd_sync_triggered",
        }
        assert required_keys.issubset(result.keys())

    def test_runbook_has_kubectl_commands(self, sample_crashloop_data):
        """Le runbook doit contenir des commandes kubectl executables."""
        result = agent._keyword_fallback(sample_crashloop_data)
        commands = [step["command"] for step in result["runbook"]]
        assert any("kubectl" in cmd for cmd in commands)


# ════════════════════════════════════════════════════════════════════════════
# _derive_deployment_name : extraction depuis le nom de pod
# ════════════════════════════════════════════════════════════════════════════

class TestDeriveDeploymentName:

    def test_standard_pod_name(self):
        # Format Kubernetes : <deploy>-<rs-hash>-<pod-hash>
        assert agent._derive_deployment_name("crash-app-6d9dcddc79-zfkl9") == "crash-app"

    def test_pod_name_with_hyphens_in_deployment(self):
        assert agent._derive_deployment_name("my-app-prod-6d9dcddc79-zfkl9") == "my-app-prod"

    def test_falls_back_if_format_unusual(self):
        # Si pas le format <deploy>-<hash>-<hash>, retourne tel quel
        assert agent._derive_deployment_name("simple-pod") == "simple-pod"


# ════════════════════════════════════════════════════════════════════════════
# _format_investigation : assemblage du prompt pour le LLM
# ════════════════════════════════════════════════════════════════════════════

class TestFormatInvestigation:

    def test_includes_all_non_empty_sections(self, sample_crashloop_data):
        text = agent._format_investigation(sample_crashloop_data)
        assert "POD STATUS" in text
        assert "POD LOGS" in text
        assert "POD DESCRIBE" in text
        assert "NAMESPACE EVENTS" in text

    def test_skips_empty_sections(self):
        partial = {"pod_status": "OK", "pod_logs": "(empty output)"}
        text = agent._format_investigation(partial)
        assert "POD STATUS" in text
        # La section vide ne doit pas apparaitre
        assert "POD LOGS" not in text

    def test_returns_string_for_empty_dict(self):
        text = agent._format_investigation({})
        # Doit retourner une chaine non vide (message de fallback)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_truncates_long_content(self):
        big_logs = "A" * 5000
        text = agent._format_investigation({"pod_logs": big_logs})
        # Le contenu doit etre tronque a 2000 chars max par section
        assert text.count("A") <= 2000


# ════════════════════════════════════════════════════════════════════════════
# Constantes critiques (garde-fous architecturaux)
# ════════════════════════════════════════════════════════════════════════════

class TestCriticalConstants:

    def test_allowed_classifications_has_exactly_7_classes(self):
        expected = {
            "CrashLoopBackOff", "OOMKilled", "ImagePullBackOff",
            "ConfigError", "ResourceExhausted", "NetworkError", "Unknown",
        }
        assert agent.ALLOWED_CLASSIFICATIONS == expected

    def test_argocd_sync_only_for_restart(self):
        """
        GARDE-FOU ANTI-BOUCLE : scale_to_zero NE doit JAMAIS declencher sync ArgoCD.
        Sinon ArgoCD reapplique replicas=1 et la remediation est annulee.
        """
        assert agent.ARGOCD_SYNC_AFTER_FIX == {"restart"}
        assert "scale_to_zero" not in agent.ARGOCD_SYNC_AFTER_FIX
        assert "none" not in agent.ARGOCD_SYNC_AFTER_FIX

    def test_policy_violation_not_in_allowed(self):
        """Le validator doit rejeter 'PolicyViolation' (hallucination LLM)."""
        assert "PolicyViolation" not in agent.ALLOWED_CLASSIFICATIONS


# ════════════════════════════════════════════════════════════════════════════
# _persist_response : ecriture JSONL
# ════════════════════════════════════════════════════════════════════════════

class TestPersistResponse:

    def test_appends_to_log(self, isolated_incidents_log, sample_agent_response_dict):
        agent._persist_response(sample_agent_response_dict)
        agent._persist_response(sample_agent_response_dict)
        lines = isolated_incidents_log.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_each_line_is_valid_json(self, isolated_incidents_log, sample_agent_response_dict):
        import json
        agent._persist_response(sample_agent_response_dict)
        for line in isolated_incidents_log.read_text().strip().split("\n"):
            parsed = json.loads(line)
            assert parsed["classification"] == "CrashLoopBackOff"

    def test_silent_on_io_error(self, monkeypatch):
        """Si l'ecriture echoue, l'agent ne doit PAS crasher (juste log warning)."""
        monkeypatch.setattr(agent, "INCIDENTS_LOG", "/non/existent/dir/file.jsonl")
        # Ne doit pas lever d'exception
        agent._persist_response({"foo": "bar"})
