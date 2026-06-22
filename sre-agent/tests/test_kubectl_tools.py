"""
Tests des utilitaires kubectl_tools.py.
On NE teste PAS les vrais appels kubectl (necessitent un cluster) — uniquement
les helpers de manipulation de strings + le fallback de resolve_pod_name.
"""
import pytest
from tools import kubectl_tools


class TestClean:
    """_clean() doit retirer les quotes et espaces que les LLMs ajoutent parfois."""

    def test_strips_double_quotes(self):
        assert kubectl_tools._clean('"demo"') == "demo"

    def test_strips_single_quotes(self):
        assert kubectl_tools._clean("'demo'") == "demo"

    def test_strips_whitespace(self):
        assert kubectl_tools._clean("  demo  ") == "demo"

    def test_strips_mixed(self):
        assert kubectl_tools._clean('  "demo"  ') == "demo"


class TestResolvePodName:
    """
    resolve_pod_name doit retourner le prefix si aucun pod ne matche (fallback safe).
    On mocke _run_kubectl pour eviter d'appeler le vrai cluster.
    """

    def test_fallback_when_no_pods_found(self, monkeypatch):
        # kubectl retourne ERROR → fallback : retourne le prefix tel quel
        monkeypatch.setattr(kubectl_tools, "_run_kubectl",
                            lambda args, timeout=30: "ERROR: no pods found")
        result = kubectl_tools.resolve_pod_name("demo", "crash-app")
        assert result == "crash-app"

    def test_exact_match(self, monkeypatch):
        monkeypatch.setattr(kubectl_tools, "_run_kubectl",
                            lambda args, timeout=30: "crash-app\nother-pod")
        result = kubectl_tools.resolve_pod_name("demo", "crash-app")
        assert result == "crash-app"

    def test_prefix_match(self, monkeypatch):
        # crash-app-6d9-zfkl5 commence par 'crash-app-'
        monkeypatch.setattr(kubectl_tools, "_run_kubectl",
                            lambda args, timeout=30: "crash-app-6d9-zfkl5\nother-pod")
        result = kubectl_tools.resolve_pod_name("demo", "crash-app")
        assert result == "crash-app-6d9-zfkl5"

    def test_no_match_returns_prefix(self, monkeypatch):
        # Aucun pod ne commence par 'crash-app' → fallback
        monkeypatch.setattr(kubectl_tools, "_run_kubectl",
                            lambda args, timeout=30: "other-pod-1\nother-pod-2")
        result = kubectl_tools.resolve_pod_name("demo", "crash-app")
        assert result == "crash-app"
