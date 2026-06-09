"""
SRE Copilot — FastAPI service.

Endpoints:
  POST /alert           — Receives Alertmanager webhook payload (main entry point)
  POST /analyze         — Analyze a single alert (direct integration / testing)
  GET  /health          — Liveness probe
  GET  /status          — Ollama connectivity and model availability check
  POST /test-crash-loop — Simulate a CrashLoopBackOff alert (dev/demo)
  GET  /dashboard       — HTML dashboard with stats and incidents history
  GET  /api/incidents   — JSON list of all persisted investigations
  GET  /api/stats       — Aggregated stats (counts, MTTR, success rate)
  GET  /metrics         — Prometheus metrics (Mission 5)
"""
import asyncio
import json
import logging
import os
from collections import Counter
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from models import AlertManagerPayload, Alert, AgentResponse
from agent import run_sre_investigation
from tools.kubectl_tools import resolve_pod_name
import metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "mistral")
GITOPS_REPO_PATH = os.getenv("GITOPS_REPO_PATH", "/gitops-repo")
INCIDENTS_LOG    = os.path.join(GITOPS_REPO_PATH, "incidents", "responses.jsonl")

# Semaphore: only 1 Mistral investigation at a time (CPU-bound on local host).
# Prevents memory exhaustion and model contention when Alertmanager sends bursts.
_investigation_lock = asyncio.Semaphore(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"SRE Copilot starting — Ollama: {OLLAMA_BASE_URL} | Model: {OLLAMA_MODEL}")
    metrics.agent_info.labels(version="2.0.0", ollama_model=OLLAMA_MODEL).set(1)
    yield
    logger.info("SRE Copilot shutting down.")

app = FastAPI(
    title="SRE Copilot",
    description="AI-powered SRE agent for Kubernetes incident response and GitOps remediation",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Health & Status ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "sre-copilot"}


@app.get("/status")
async def status():
    """Check Ollama connectivity and model availability."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            model_ok = any(OLLAMA_MODEL in m for m in models)
            return {
                "status":          "ok" if model_ok else "degraded",
                "ollama":          "reachable",
                "model":           OLLAMA_MODEL,
                "model_available": model_ok,
                "available_models": models,
            }
    except Exception as exc:
        return {
            "status": "degraded",
            "ollama": "unreachable",
            "error":  str(exc),
            "hint":   f"Run: ollama pull {OLLAMA_MODEL}",
        }


# ── Alert processing ───────────────────────────────────────────────────────────

@app.post("/alert", response_model=dict)
async def receive_alertmanager_webhook(payload: AlertManagerPayload):
    """
    Main webhook endpoint for Alertmanager.
    Processes all firing alerts sequentially under a semaphore so only one
    Mistral inference runs at a time (avoids CPU/memory contention).
    """
    firing = [a for a in payload.alerts if a.status == "firing"]
    if not firing:
        logger.info("Webhook received — no firing alerts, nothing to do.")
        return {"message": "No firing alerts.", "count": 0}

    logger.info(f"Webhook received — {len(firing)} firing alert(s)")
    results = []

    for alert in firing:
        logger.info(f"Queuing investigation: {alert.labels.alertname} / {alert.labels.namespace}")
        async with _investigation_lock:
            response = await run_sre_investigation(alert)
        results.append(response.model_dump())
        logger.info(
            f"Investigation complete: {alert.labels.alertname} → "
            f"classification={response.classification}"
        )

    return {
        "message": f"Processed {len(results)} alert(s)",
        "results": results,
    }


@app.post("/analyze", response_model=AgentResponse)
async def analyze_alert(alert: Alert):
    """Analyze a single alert directly. Used for testing and direct integrations."""
    logger.info(f"Direct analysis: {alert.labels.alertname}")
    async with _investigation_lock:
        return await run_sre_investigation(alert)


# ── Dev / Demo endpoints ───────────────────────────────────────────────────────

@app.post("/test-crash-loop")
async def test_crash_loop():
    """
    Simulate a CrashLoopBackOff alert using the real crash-app pod running in
    the demo namespace. Resolves the actual pod name dynamically so investigation
    data is real (not mocked).
    """
    pod_name = resolve_pod_name("demo", "crash-app")
    logger.info(f"test-crash-loop: resolved pod = {pod_name}")

    test_alert = Alert(
        status="firing",
        labels={
            "alertname": "PodRestartingTooMuch",
            "namespace":  "demo",
            "pod":         pod_name,
            "severity":   "critical",
        },
        annotations={
            "summary":     "Pod restarting frequently",
            "description": f"Pod {pod_name} in namespace demo is restarting too often.",
        },
    )
    async with _investigation_lock:
        return await run_sre_investigation(test_alert)


# ── Dashboard ──────────────────────────────────────────────────────────────────

def _read_incidents() -> list[dict]:
    """Read all persisted incidents from the JSONL log. Newest first."""
    if not os.path.exists(INCIDENTS_LOG):
        return []
    incidents = []
    with open(INCIDENTS_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                incidents.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    incidents.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return incidents


def _compute_stats(incidents: list[dict]) -> dict:
    """Aggregate stats across all incidents."""
    total = len(incidents)
    if total == 0:
        return {
            "total":              0,
            "auto_remediated":    0,
            "argocd_synced":      0,
            "success_rate":       0.0,
            "mttr_seconds":       0.0,
            "classifications":    {},
            "namespaces":         {},
            "severities":         {},
            "remediated_per_day": {},
        }

    auto_remediated = sum(1 for i in incidents if i.get("auto_remediation_applied"))
    argocd_synced   = sum(1 for i in incidents if i.get("argocd_sync_triggered"))
    durations       = [i.get("duration_seconds") for i in incidents if i.get("duration_seconds") is not None]
    mttr            = round(sum(durations) / len(durations), 2) if durations else 0.0

    classifications = Counter(i.get("classification", "Unknown") for i in incidents)
    namespaces      = Counter(i.get("namespace", "unknown")      for i in incidents)
    severities      = Counter(i.get("severity", "unknown")       for i in incidents)

    by_day = Counter()
    for i in incidents:
        ts = i.get("timestamp", "")
        if len(ts) >= 10:
            by_day[ts[:10]] += 1

    return {
        "total":              total,
        "auto_remediated":    auto_remediated,
        "argocd_synced":      argocd_synced,
        "success_rate":       round(100.0 * auto_remediated / total, 1) if total else 0.0,
        "mttr_seconds":       mttr,
        "classifications":    dict(classifications),
        "namespaces":         dict(namespaces),
        "severities":         dict(severities),
        "remediated_per_day": dict(sorted(by_day.items())),
    }


@app.get("/api/incidents")
async def list_incidents(limit: int = 100):
    """Return the last N incidents as JSON (newest first)."""
    incidents = _read_incidents()
    return {"count": len(incidents), "incidents": incidents[:limit]}


@app.get("/api/stats")
async def get_stats():
    """Return aggregated statistics across all incidents."""
    return _compute_stats(_read_incidents())


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the SRE Copilot dashboard HTML page."""
    return HTMLResponse(content=_DASHBOARD_HTML)


# ── Prometheus metrics (Mission 5) ─────────────────────────────────────────────

@app.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus-format metrics. Scraped by kube-prometheus-stack."""
    body, ctype = metrics.render_metrics()
    return Response(content=body, media_type=ctype)


_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SRE Copilot</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
<style>
  /* ── Design tokens (inspired by Impeccable: OKLCH neutrals, no gradients) ── */
  :root {
    /* Tinted neutrals — warm, slightly desaturated */
    --bg:           oklch(98.5% 0.003 80);
    --surface:      oklch(100% 0 0);
    --surface-alt:  oklch(97% 0.005 80);
    --border:       oklch(91% 0.006 80);
    --border-soft:  oklch(94% 0.005 80);
    --text:         oklch(20% 0.015 80);
    --text-muted:   oklch(50% 0.012 80);
    --text-soft:    oklch(65% 0.01 80);

    /* Single accent — warm ochre/yellow (Impeccable signature) */
    --accent:       oklch(72% 0.13 75);
    --accent-soft:  oklch(95% 0.04 82);
    --accent-text:  oklch(40% 0.12 70);

    /* Semantic — used sparingly */
    --success:      oklch(58% 0.13 145);
    --success-soft: oklch(95% 0.04 145);
    --danger:       oklch(55% 0.18 25);
    --danger-soft:  oklch(95% 0.04 25);
    --warn:         oklch(65% 0.14 60);
    --warn-soft:    oklch(95% 0.04 80);

    /* Type scale */
    --font-sans:  "Avenir Next", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    --font-mono:  "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;

    /* 7-step spacing scale */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 24px;
    --space-6: 32px;
    --space-7: 48px;

    /* Radii — 8px small, 12px medium (no big rounded squares) */
    --radius-sm: 6px;
    --radius:    10px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: var(--font-sans);
    background: var(--bg);
    color: var(--text);
    font-size: 15px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    font-feature-settings: "ss01", "cv11";
  }
  body > .container { max-width: 1240px; margin: 0 auto; padding: var(--space-6) var(--space-5); }

  /* Lucide icon defaults */
  .icon {
    width: 16px; height: 16px;
    stroke-width: 1.75;
    flex-shrink: 0;
    display: inline-block;
    vertical-align: middle;
  }
  .icon-lg { width: 20px; height: 20px; }
  .icon-sm { width: 14px; height: 14px; }

  /* ── Header ─────────────────────────────────────────────────────── */
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    padding-bottom: var(--space-5);
    margin-bottom: var(--space-6);
    border-bottom: 1px solid var(--border);
  }
  header h1 {
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.015em;
    color: var(--text);
  }
  header .eyebrow {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent-text);
    margin-bottom: var(--space-1);
  }
  header .controls { display: flex; gap: var(--space-3); align-items: center; }

  /* ── Buttons ────────────────────────────────────────────────────── */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    height: 32px;
    padding: 0 var(--space-3);
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-family: inherit;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 120ms ease, border-color 120ms ease;
  }
  .btn:hover  { background: var(--surface-alt); border-color: var(--text-soft); }
  .btn:active { background: var(--border-soft); }
  .btn-ghost  { background: transparent; border-color: transparent; color: var(--text-muted); }
  .btn-ghost:hover { background: var(--surface-alt); color: var(--text); }

  .last-update { font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }

  .toggle {
    display: inline-flex; align-items: center; gap: var(--space-2);
    font-size: 13px; color: var(--text-muted); cursor: pointer; user-select: none;
  }
  .toggle input { accent-color: var(--accent); cursor: pointer; }

  /* ── Stats row ──────────────────────────────────────────────────── */
  .stats {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: var(--space-3);
    margin-bottom: var(--space-6);
  }
  @media (max-width: 1000px) { .stats { grid-template-columns: repeat(2, 1fr); } }

  .stat {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: var(--space-4) var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .stat-head {
    display: flex; align-items: center; justify-content: space-between;
    color: var(--text-muted);
  }
  .stat-label { font-size: 12px; font-weight: 500; color: var(--text-muted); }
  .stat-value {
    font-size: 28px; font-weight: 600; color: var(--text);
    letter-spacing: -0.02em; font-variant-numeric: tabular-nums;
  }
  .stat-unit { font-size: 14px; color: var(--text-muted); margin-left: 2px; font-weight: 400; }
  .stat-icon { color: var(--text-soft); }

  /* ── Cards (charts, incidents) ──────────────────────────────────── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: var(--space-5);
  }
  .card-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: var(--space-4);
  }
  .card-title {
    font-size: 13px; font-weight: 600; color: var(--text);
    display: flex; align-items: center; gap: var(--space-2);
  }
  .card-title .icon { color: var(--text-muted); }

  /* ── Charts row ─────────────────────────────────────────────────── */
  .charts {
    display: grid;
    grid-template-columns: 1fr 1.6fr;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }
  @media (max-width: 900px) { .charts { grid-template-columns: 1fr; } }
  .chart-wrap { position: relative; height: 240px; }

  /* ── Incidents list ─────────────────────────────────────────────── */
  .search {
    display: flex; align-items: center; gap: var(--space-2);
    padding: 0 var(--space-3);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    width: 280px;
    transition: border-color 120ms ease;
  }
  .search:focus-within { border-color: var(--accent); }
  .search .icon { color: var(--text-muted); }
  .search input {
    border: none; outline: none; background: transparent;
    width: 100%; height: 32px;
    font-family: inherit; font-size: 13px; color: var(--text);
  }
  .search input::placeholder { color: var(--text-soft); }

  .incident {
    border-top: 1px solid var(--border-soft);
  }
  .incident:first-child { border-top: 1px solid var(--border); }

  .incident-row {
    display: grid;
    grid-template-columns: 16px 160px 200px minmax(0, 1fr) 96px 132px;
    gap: var(--space-4);
    align-items: center;
    padding: var(--space-3) var(--space-1);
    cursor: pointer;
    transition: background 120ms ease;
  }
  .incident-row:hover { background: var(--surface-alt); }
  .incident.open > .incident-row { background: var(--surface-alt); }

  .chev {
    color: var(--text-soft);
    transition: transform 160ms ease;
  }
  .incident.open .chev { transform: rotate(90deg); }

  .meta-time {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  .meta-class {
    font-weight: 600; font-size: 14px; color: var(--text);
    letter-spacing: -0.005em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    display: flex; align-items: center; gap: var(--space-2);
  }
  .meta-pod {
    font-family: var(--font-mono); font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    min-width: 0;
  }

  /* ── Badges (status pills) ──────────────────────────────────────── */
  .badge {
    display: inline-flex; align-items: center; justify-content: center;
    gap: 4px;
    height: 22px; padding: 0 var(--space-2);
    border-radius: 999px;
    font-size: 11px; font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
    border: 1px solid transparent;
  }
  .badge .icon { width: 12px; height: 12px; stroke-width: 2; }

  .badge-critical { color: var(--danger);   background: var(--danger-soft);  border-color: oklch(85% 0.05 25); }
  .badge-warning  { color: var(--warn);     background: var(--warn-soft);    border-color: oklch(85% 0.05 60); }
  .badge-info     { color: var(--accent-text); background: var(--accent-soft); border-color: oklch(85% 0.05 82); }
  .badge-ok       { color: var(--success);  background: var(--success-soft); border-color: oklch(82% 0.05 145); }
  .badge-skip     { color: var(--text-muted); background: var(--surface-alt); border-color: var(--border); }

  /* ── Incident body (expanded view) ──────────────────────────────── */
  .incident-body {
    display: none;
    padding: var(--space-5);
    background: var(--surface-alt);
    border-top: 1px solid var(--border);
  }
  .incident.open > .incident-body { display: block; }

  .field { margin-bottom: var(--space-4); }
  .field:last-child { margin-bottom: 0; }
  .field-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: var(--space-2);
    display: flex; align-items: center; gap: var(--space-2);
  }
  .field-label .icon { width: 13px; height: 13px; color: var(--text-soft); }
  .field-value { font-size: 14px; color: var(--text); line-height: 1.6; word-break: break-word; }

  .runbook-step {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: var(--space-3);
    margin-bottom: var(--space-2);
  }
  .runbook-step .step-action {
    font-weight: 600; font-size: 13px; color: var(--text);
    display: flex; align-items: center; gap: var(--space-2);
  }
  .runbook-step .step-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 18px; height: 18px;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent-text);
    font-size: 10px; font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .runbook-step .step-cmd {
    font-family: var(--font-mono);
    font-size: 12px;
    background: oklch(15% 0.005 80);
    color: oklch(92% 0.02 80);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    margin: var(--space-2) 0;
    overflow-x: auto;
    white-space: pre;
    line-height: 1.55;
  }
  .runbook-step .step-desc {
    font-size: 13px; color: var(--text-muted); line-height: 1.55;
  }

  .raw-json {
    background: oklch(15% 0.005 80);
    color: oklch(86% 0.05 145);
    padding: var(--space-3);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono); font-size: 12px;
    max-height: 320px; overflow: auto;
    white-space: pre-wrap; word-break: break-word;
    line-height: 1.55;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-3);
  }
  .metric-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: var(--space-3);
  }
  .metric-item .label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--text-muted);
    margin-bottom: var(--space-1);
    display: flex; align-items: center; gap: 6px;
  }
  .metric-item .label .icon { width: 12px; height: 12px; }
  .metric-item .value {
    font-size: 14px; color: var(--text); font-weight: 500;
    word-break: break-all;
  }

  /* ── Empty states ───────────────────────────────────────────────── */
  .empty {
    text-align: center;
    padding: var(--space-7) var(--space-5);
    color: var(--text-muted);
  }
  .empty .icon { width: 32px; height: 32px; color: var(--text-soft); margin-bottom: var(--space-3); }
  .empty p { font-size: 14px; }
  .empty small {
    display: block; margin-top: var(--space-2);
    font-size: 12px; color: var(--text-soft);
  }

  /* ── Footer ─────────────────────────────────────────────────────── */
  footer {
    margin-top: var(--space-7);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border);
    text-align: center;
    color: var(--text-soft);
    font-size: 11px;
  }
  footer code {
    font-family: var(--font-mono);
    background: var(--surface-alt);
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid var(--border-soft);
  }

  /* ── Responsive ─────────────────────────────────────────────────── */
  @media (max-width: 1100px) {
    .incident-row { grid-template-columns: 16px 140px minmax(0, 1fr) 90px 132px; }
    .meta-class { display: none; }
  }
  @media (max-width: 700px) {
    body > .container { padding: var(--space-4); }
    header { flex-direction: column; align-items: flex-start; gap: var(--space-3); }
    .incident-row { grid-template-columns: 16px minmax(0, 1fr) 132px; }
    .meta-time, .meta-pod { display: none; }
    .search { width: 100%; }
    .metrics-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<div class="container">

  <header>
    <div>
      <div class="eyebrow">SRE Copilot · PFE IFS 013/26</div>
      <h1>Incidents &amp; remédiation automatique</h1>
    </div>
    <div class="controls">
      <span id="last-update" class="last-update">—</span>
      <button class="btn" onclick="loadAll()" title="Rafraîchir">
        <i data-lucide="refresh-cw" class="icon"></i>
        <span>Rafraîchir</span>
      </button>
      <label class="toggle">
        <input type="checkbox" id="auto-refresh" checked>
        Auto 30s
      </label>
    </div>
  </header>

  <section class="stats" id="stats"></section>

  <section class="charts">
    <div class="card">
      <div class="card-head">
        <div class="card-title">
          <i data-lucide="pie-chart" class="icon"></i>
          Classifications
        </div>
      </div>
      <div class="chart-wrap" id="wrap-class"><canvas id="chart-class"></canvas></div>
    </div>
    <div class="card">
      <div class="card-head">
        <div class="card-title">
          <i data-lucide="bar-chart-3" class="icon"></i>
          Volume par jour
        </div>
      </div>
      <div class="chart-wrap" id="wrap-timeline"><canvas id="chart-timeline"></canvas></div>
    </div>
  </section>

  <section class="card">
    <div class="card-head">
      <div class="card-title">
        <i data-lucide="list" class="icon"></i>
        Incidents récents
        <span class="last-update" id="incidents-count"></span>
      </div>
      <div class="search">
        <i data-lucide="search" class="icon icon-sm"></i>
        <input type="text" id="q" placeholder="Filtrer par classification, pod, namespace…" oninput="renderFiltered()">
      </div>
    </div>
    <div id="incidents-list"></div>
  </section>

  <footer>
    SRE Copilot — données persistées dans <code>/gitops-repo/incidents/responses.jsonl</code>
  </footer>

</div>

<script>
let chartClass = null, chartTimeline = null;
let allIncidents = [];

// Icon used in stat cards (paired with label)
const STAT_ICONS = {
  total:     'activity',
  remediated:'check-circle-2',
  rate:      'gauge',
  mttr:      'clock',
  argocd:    'git-branch',
};

async function loadStats() {
  const r = await fetch('/api/stats');
  const s = await r.json();
  renderStats(s);
  renderClass(s.classifications);
  renderTimeline(s.remediated_per_day);
}

async function loadIncidents() {
  const r = await fetch('/api/incidents?limit=100');
  const data = await r.json();
  allIncidents = data.incidents;
  renderFiltered();
}

async function loadAll() {
  try {
    await Promise.all([loadStats(), loadIncidents()]);
    document.getElementById('last-update').textContent =
      'Mis à jour ' + new Date().toLocaleTimeString('fr-FR');
    lucide.createIcons();
  } catch (e) {
    console.error(e);
    document.getElementById('last-update').textContent = 'Erreur — ' + e.message;
  }
}

function renderStats(s) {
  const cards = [
    { key: 'total',      label: 'Incidents',     value: s.total,           unit: '' },
    { key: 'remediated', label: 'Auto-remédiés', value: s.auto_remediated, unit: '' },
    { key: 'rate',       label: 'Taux de succès', value: s.success_rate,   unit: '%' },
    { key: 'mttr',       label: 'MTTR moyen',    value: s.mttr_seconds,    unit: 's' },
    { key: 'argocd',     label: 'ArgoCD sync',   value: s.argocd_synced,   unit: '' },
  ];
  document.getElementById('stats').innerHTML = cards.map(c => `
    <div class="stat">
      <div class="stat-head">
        <span class="stat-label">${c.label}</span>
        <i data-lucide="${STAT_ICONS[c.key]}" class="icon stat-icon"></i>
      </div>
      <div class="stat-value">${c.value}<span class="stat-unit">${c.unit}</span></div>
    </div>
  `).join('');
}

// Chart palette — warm, single-family. No rainbow gradients.
const PALETTE = [
  'oklch(72% 0.13 75)',   // accent (ochre)
  'oklch(58% 0.13 145)',  // success
  'oklch(55% 0.18 25)',   // danger
  'oklch(65% 0.14 240)',  // blue (rare)
  'oklch(50% 0.10 280)',  // purple (rare)
  'oklch(55% 0.08 40)',   // brown
];

function renderClass(data) {
  const labels = Object.keys(data);
  const values = Object.values(data);
  const wrap = document.getElementById('wrap-class');
  if (labels.length === 0) {
    wrap.innerHTML = emptyChartHtml('chart-pie', 'Pas encore de données');
    lucide.createIcons();
    return;
  }
  if (!wrap.querySelector('canvas')) {
    wrap.innerHTML = '<canvas id="chart-class"></canvas>';
  }
  if (chartClass) chartClass.destroy();
  chartClass = new Chart(document.getElementById('chart-class'), {
    type: 'doughnut',
    data: { labels, datasets: [{
      data: values,
      backgroundColor: PALETTE,
      borderWidth: 2,
      borderColor: 'white',
    }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '64%',
      plugins: {
        legend: { position: 'right', labels: { font: { size: 12, family: getComputedStyle(document.body).fontFamily }, padding: 12, color: 'oklch(35% 0.012 80)' } }
      }
    }
  });
}

function renderTimeline(data) {
  const labels = Object.keys(data);
  const values = Object.values(data);
  const wrap = document.getElementById('wrap-timeline');
  if (labels.length === 0) {
    wrap.innerHTML = emptyChartHtml('trending-up', 'Pas encore de données');
    lucide.createIcons();
    return;
  }
  if (!wrap.querySelector('canvas')) {
    wrap.innerHTML = '<canvas id="chart-timeline"></canvas>';
  }
  if (chartTimeline) chartTimeline.destroy();
  chartTimeline = new Chart(document.getElementById('chart-timeline'), {
    type: 'bar',
    data: { labels, datasets: [{
      label: 'Incidents',
      data: values,
      backgroundColor: 'oklch(72% 0.13 75)',
      borderRadius: 4,
      maxBarThickness: 32,
    }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: 'oklch(50% 0.012 80)', font: { size: 11 } } },
        y: { beginAtZero: true, ticks: { stepSize: 1, precision: 0, color: 'oklch(50% 0.012 80)', font: { size: 11 } }, grid: { color: 'oklch(94% 0.005 80)' } }
      }
    }
  });
}

function emptyChartHtml(icon, msg) {
  return `<div class="empty">
    <i data-lucide="${icon}" class="icon"></i>
    <p>${msg}</p>
  </div>`;
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function severityIcon(sev) {
  const s = (sev || '').toLowerCase();
  if (s === 'critical') return 'alert-octagon';
  if (s === 'warning')  return 'alert-triangle';
  return 'info';
}

function renderFiltered() {
  const q = (document.getElementById('q').value || '').toLowerCase().trim();
  const filtered = q
    ? allIncidents.filter(i =>
        (i.classification || '').toLowerCase().includes(q) ||
        (i.namespace || '').toLowerCase().includes(q) ||
        (i.pod || '').toLowerCase().includes(q) ||
        (i.alert_name || '').toLowerCase().includes(q) ||
        (i.severity || '').toLowerCase().includes(q)
      )
    : allIncidents;
  renderIncidents(filtered, allIncidents.length);
  lucide.createIcons();
}

function renderIncidents(items, total) {
  document.getElementById('incidents-count').textContent = `· ${items.length} / ${total}`;
  const list = document.getElementById('incidents-list');
  if (items.length === 0) {
    list.innerHTML = total === 0
      ? `<div class="empty">
          <i data-lucide="inbox" class="icon"></i>
          <p>Aucun incident traité pour le moment.</p>
          <small>Lance une simulation : <code>POST http://localhost:8001/test-crash-loop</code></small>
        </div>`
      : `<div class="empty"><i data-lucide="search-x" class="icon"></i><p>Aucun incident ne correspond à la recherche.</p></div>`;
    return;
  }
  list.innerHTML = items.map((i, idx) => {
    const sev   = (i.severity || 'info').toLowerCase();
    const sevIcon = severityIcon(sev);
    const time  = i.timestamp ? new Date(i.timestamp).toLocaleString('fr-FR') : '—';
    const podFull = `${i.namespace || '?'}/${i.pod || '?'}`;
    const remediated = i.auto_remediation_applied
      ? `<span class="badge badge-ok"><i data-lucide="check" class="icon"></i>Remédié</span>`
      : `<span class="badge badge-skip"><i data-lucide="minus" class="icon"></i>Non appliqué</span>`;
    const runbookHtml = (i.runbook || []).map(s => `
      <div class="runbook-step">
        <div class="step-action">
          <span class="step-num">${escapeHtml(s.order)}</span>
          ${escapeHtml(s.action)}
        </div>
        ${s.command ? `<div class="step-cmd">${escapeHtml(s.command)}</div>` : ''}
        <div class="step-desc">${escapeHtml(s.description)}</div>
      </div>
    `).join('');
    return `
      <div class="incident" id="inc-${idx}">
        <div class="incident-row" onclick="document.getElementById('inc-${idx}').classList.toggle('open'); lucide.createIcons();">
          <i data-lucide="chevron-right" class="icon icon-sm chev"></i>
          <span class="meta-time" title="${escapeHtml(i.timestamp || '')}">${time}</span>
          <span class="meta-class" title="${escapeHtml(i.classification)}">
            <i data-lucide="${sevIcon}" class="icon icon-sm"></i>
            ${escapeHtml(i.classification)}
          </span>
          <span class="meta-pod" title="${escapeHtml(podFull)}">${escapeHtml(podFull)}</span>
          <span class="badge badge-${sev}">${escapeHtml(i.severity)}</span>
          ${remediated}
        </div>
        <div class="incident-body">
          <div class="field">
            <div class="field-label"><i data-lucide="tag" class="icon"></i>Alert name</div>
            <div class="field-value">${escapeHtml(i.alert_name)}</div>
          </div>
          <div class="field">
            <div class="field-label"><i data-lucide="file-text" class="icon"></i>Root cause</div>
            <div class="field-value">${escapeHtml(i.root_cause)}</div>
          </div>
          <div class="field">
            <div class="field-label"><i data-lucide="list-checks" class="icon"></i>Runbook · ${(i.runbook || []).length} étapes</div>
            <div class="field-value">${runbookHtml}</div>
          </div>
          ${i.remediation_details ? `
          <div class="field">
            <div class="field-label"><i data-lucide="wrench" class="icon"></i>Remédiation appliquée</div>
            <div class="field-value">${escapeHtml(i.remediation_details)}</div>
          </div>` : ''}
          <div class="field">
            <div class="field-label"><i data-lucide="gauge" class="icon"></i>Métriques</div>
            <div class="metrics-grid">
              <div class="metric-item">
                <div class="label"><i data-lucide="timer" class="icon"></i>Durée</div>
                <div class="value">${i.duration_seconds || '?'} s</div>
              </div>
              <div class="metric-item">
                <div class="label"><i data-lucide="git-commit" class="icon"></i>Git</div>
                <div class="value">${escapeHtml(i.git_pr_url || 'aucun')}</div>
              </div>
              <div class="metric-item">
                <div class="label"><i data-lucide="git-branch" class="icon"></i>ArgoCD</div>
                <div class="value">${i.argocd_sync_triggered ? 'sync déclenché' : 'non'}</div>
              </div>
            </div>
          </div>
          <div class="field">
            <div class="field-label"><i data-lucide="code" class="icon"></i>Payload JSON</div>
            <pre class="raw-json">${escapeHtml(JSON.stringify(i, null, 2))}</pre>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

loadAll();
setInterval(() => {
  if (document.getElementById('auto-refresh').checked) loadAll();
}, 30000);
</script>
</body>
</html>
"""
