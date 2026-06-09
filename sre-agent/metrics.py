"""
Prometheus metrics for the SRE Copilot.
Exposed via /metrics on the FastAPI service.

KPIs:
  sre_alerts_total{classification,severity,namespace}        - alertes reçues
  sre_remediated_total{classification,fix_type,result}       - remédiations tentées
  sre_investigation_duration_seconds                          - durée d'une investigation (histogram)
  sre_argocd_sync_total{result}                              - appels ArgoCD sync (success/skipped/error)
  sre_llm_fallback_total{reason}                             - bascules en keyword fallback
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

# Registry dédié pour ne pas mélanger avec les métriques par défaut de prometheus_client
registry = CollectorRegistry()

# ── Compteurs ─────────────────────────────────────────────────────────────────

alerts_total = Counter(
    "sre_alerts_total",
    "Nombre total d'alertes reçues et analysées par le SRE Agent.",
    labelnames=("classification", "severity", "namespace"),
    registry=registry,
)

remediated_total = Counter(
    "sre_remediated_total",
    "Nombre de remédiations automatiques tentées (auto_remediation_applied).",
    labelnames=("classification", "fix_type", "result"),  # result: success|skipped|failed
    registry=registry,
)

argocd_sync_total = Counter(
    "sre_argocd_sync_total",
    "Appels ArgoCD sync depuis l'agent.",
    labelnames=("result",),  # success|skipped|failed
    registry=registry,
)

llm_fallback_total = Counter(
    "sre_llm_fallback_total",
    "Bascules en keyword fallback (LLM down ou réponse invalide).",
    labelnames=("reason",),  # llm_error|invalid_classification
    registry=registry,
)

# ── Histogrammes ──────────────────────────────────────────────────────────────

investigation_duration = Histogram(
    "sre_investigation_duration_seconds",
    "Durée d'une investigation complète (Phase 1 + 2 + 3).",
    buckets=(5, 10, 30, 60, 90, 120, 180, 240, 360, 600),
    registry=registry,
)

# ── Gauges ────────────────────────────────────────────────────────────────────

agent_info = Gauge(
    "sre_agent_info",
    "Métadonnées de l'agent (toujours 1, labels portent l'info).",
    labelnames=("version", "ollama_model"),
    registry=registry,
)


def record_investigation(response: dict, fix_type: str = "none") -> None:
    """Met à jour toutes les métriques à partir du AgentResponse à la fin de Phase 3."""
    classification = response.get("classification", "Unknown")
    severity       = response.get("severity", "unknown")
    namespace      = response.get("namespace", "unknown")
    duration       = response.get("duration_seconds")
    auto_applied   = response.get("auto_remediation_applied", False)
    argocd_synced  = response.get("argocd_sync_triggered", False)

    alerts_total.labels(classification, severity, namespace).inc()

    if duration is not None:
        investigation_duration.observe(duration)

    if fix_type and fix_type != "none":
        result = "success" if auto_applied else "failed"
        remediated_total.labels(classification, fix_type, result).inc()
    else:
        remediated_total.labels(classification, "none", "skipped").inc()

    # ArgoCD : success si déclenché, skipped sinon (fix_type=none ou scale_to_zero)
    argocd_sync_total.labels("success" if argocd_synced else "skipped").inc()


def render_metrics() -> tuple[bytes, str]:
    """Retourne (body, content_type) pour l'endpoint /metrics."""
    return generate_latest(registry), CONTENT_TYPE_LATEST
