"""
HTML templates servis par main.py :
  - DASHBOARD_HTML       : page principale (theme PwC)
  - AUDIT_REPORT_HTML    : rapport d'audit imprimable (24h par defaut)

Pourquoi un module separe ? main.py atteignait 1100+ lignes. Externaliser le
HTML rend le code Python plus lisible et accelere l'iteration sur le design.
"""

# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD — Theme PwC (orange #DC6900, serif headlines, white cards)
# ════════════════════════════════════════════════════════════════════════════

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SRE Copilot — Agent Workspace</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    /* PwC brand palette */
    --pwc-orange:        #DC6900;
    --pwc-orange-dark:   #B85A00;
    --pwc-orange-light:  #FFE4CC;
    --pwc-orange-bg:     #FFF4EA;
    --pwc-cream:         #FAFAFA;

    /* Neutrals */
    --bg:         #FAFAFA;
    --surface:    #FFFFFF;
    --text:       #1F1F1F;
    --text-muted: #6B6B6B;
    --text-soft:  #8A8A8A;
    --border:     #E8E8E8;
    --border-strong: #D0D0D0;

    /* Status colors */
    --success: #2D7A3E;
    --success-bg: #E8F5EC;
    --warn: #B86E00;
    --warn-bg: #FFF4E5;
    --danger: #B81B1B;
    --danger-bg: #FBEAEA;
    --info: #1F5680;
    --info-bg: #E8F0F7;

    /* Typography */
    --font-serif: 'Source Serif 4', Georgia, 'Times New Roman', serif;
    --font-sans:  'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-mono:  'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;

    /* 7-step spacing */
    --s-1: 4px;
    --s-2: 8px;
    --s-3: 12px;
    --s-4: 16px;
    --s-5: 24px;
    --s-6: 32px;
    --s-7: 48px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: var(--font-sans);
    /* Degrade subtil rose-peche → blanc → orange clair (signature PwC) */
    background:
      radial-gradient(ellipse 60% 50% at 95% 95%, rgba(232, 93, 4, 0.18), transparent 60%),
      radial-gradient(ellipse 50% 40% at 0% 0%, rgba(255, 200, 200, 0.35), transparent 60%),
      linear-gradient(135deg, #FFF5F0 0%, #FFFFFF 50%, #FFEEE0 100%);
    background-attachment: fixed;
    color: var(--text);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
    position: relative;
    overflow-x: hidden;
  }

  /* ── Parallelogrammes oranges decoratifs (signature PwC) ─────────────── */
  body::before, body::after {
    content: "";
    position: fixed;
    width: 380px;
    height: 56px;
    background: #E85D04;
    transform: skewX(-25deg);
    pointer-events: none;
    z-index: 0;
  }
  body::before {
    /* Bar haute (plus courte) */
    top: 18%;
    right: -30px;
    width: 280px;
    opacity: 0.92;
  }
  body::after {
    /* Bar basse (plus longue, decalee a gauche) */
    top: calc(18% + 76px);
    right: 60px;
    width: 380px;
    opacity: 0.92;
  }
  @media (max-width: 1100px) { body::before, body::after { display: none; } }

  /* ── Layout : sidebar gauche + main ───────────────────────────────────── */
  .layout {
    display: grid;
    grid-template-columns: 260px 1fr;
    min-height: 100vh;
    position: relative;
    z-index: 1;
  }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } .sidebar { display: none; } }

  /* ── Sidebar PwC ──────────────────────────────────────────────────────── */
  .sidebar {
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-right: 1px solid var(--border);
    padding: var(--s-5) var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-5);
    position: relative;
    z-index: 3;
  }
  /* ── Brand : logo PwC officiel uniquement ─────────────────────────────── */
  .brand {
    display: flex;
    justify-content: center;
    padding: var(--s-4) 0 var(--s-2) 0;
  }
  .brand img {
    width: 80px;
    height: auto;
    display: block;
  }

  .nav { display: flex; flex-direction: column; gap: 2px; }
  .nav a {
    display: flex; align-items: center; gap: var(--s-3);
    padding: var(--s-3) var(--s-3);
    color: var(--text-muted); text-decoration: none;
    font-size: 13px; font-weight: 500;
    border-radius: 6px;
    transition: background 120ms ease, color 120ms ease;
  }
  .nav a:hover { background: var(--pwc-orange-bg); color: var(--text); }
  .nav a.active {
    background: var(--pwc-orange-bg);
    color: var(--text);
    font-weight: 600;
    border: 1px solid var(--pwc-orange-light);
  }
  .nav .icon { width: 18px; height: 18px; stroke-width: 1.75; }

  /* ── Main content ─────────────────────────────────────────────────────── */
  .main {
    padding: var(--s-6) var(--s-7);
    max-width: 1400px;
    min-width: 0;             /* empêche le débordement hors de la colonne grid */
    background: transparent;  /* laisse voir le degrade + parallelogrammes */
    position: relative;
    z-index: 2;
  }
  @media (max-width: 700px) { .main { padding: var(--s-4); } }

  /* Hero section */
  .hero { background: rgba(255,255,255,0.88); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border-radius: 12px; padding: var(--s-6); position: relative; overflow: hidden; }
  .hero-eyebrow {
    font-size: 11px; font-weight: 600; letter-spacing: 0.16em;
    color: var(--pwc-orange-dark); text-transform: uppercase; margin-bottom: var(--s-3);
  }
  .hero-title {
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 72px;
    font-weight: 700;
    line-height: 0.95;
    letter-spacing: -0.05em;
    color: #111;
}
  @media (max-width: 700px) { .hero-title { font-size: 32px; } }
  .hero-subtitle { font-size: 15px; color: var(--text-muted); max-width: 600px; line-height: 1.6; margin-bottom: var(--s-5); }
  .hero-bars {
    position: absolute; top: var(--s-6); right: var(--s-6);
    display: flex; flex-direction: column; gap: 6px;
  }
  .hero-bars span {
    height: 8px; background: var(--pwc-orange); border-radius: 2px;
    transform: skewX(-20deg); transform-origin: right center;
  }
  .hero-bars span:nth-child(1) { width: 70px; }
  .hero-bars span:nth-child(2) { width: 110px; background: var(--pwc-orange-dark); }
  @media (max-width: 700px) { .hero-bars { display: none; } }

  .hero-meta {
    display: flex; justify-content: space-between; align-items: center;
    padding-top: var(--s-4);
    border-top: 1px solid var(--border);
    flex-wrap: wrap; gap: var(--s-3);
  }
  .hero-stack { font-size: 13px; color: var(--text-muted); }
  .hero-stack b { color: var(--text); font-weight: 600; }
  .hero-actions { display: flex; gap: var(--s-3); align-items: center; }
  .last-update { font-size: 12px; color: var(--text-soft); font-variant-numeric: tabular-nums; }

  .btn {
    display: inline-flex; align-items: center; gap: var(--s-2);
    height: 36px; padding: 0 var(--s-4);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border-strong); border-radius: 6px;
    font-family: inherit; font-size: 13px; font-weight: 500;
    cursor: pointer; text-decoration: none;
    transition: all 120ms ease;
  }
  .btn:hover { background: var(--pwc-orange-bg); border-color: var(--pwc-orange); }
  .btn .icon { width: 14px; height: 14px; stroke-width: 2; }
  .btn-primary {
    background: var(--pwc-orange); color: white; border-color: var(--pwc-orange);
  }
  .btn-primary:hover { background: var(--pwc-orange-dark); border-color: var(--pwc-orange-dark); }

  /* ── KPI cards ────────────────────────────────────────────────────────── */
  .kpi-grid{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:4px;
}
  @media (max-width: 1200px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 600px)  { .kpi-grid { grid-template-columns: 1fr; } }

  .kpi {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: var(--s-5);
    transition: border-color 120ms ease, box-shadow 120ms ease;
  }
  .kpi:hover { border-color: var(--pwc-orange-light); box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
  .kpi-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--s-3); }
  .kpi-label { font-size: 13px; font-weight: 500; color: var(--text-muted); }
  .kpi-icon-bg {
    width: 36px; height: 36px; border-radius: 8px;
    background: var(--pwc-orange-bg); color: var(--pwc-orange);
    display: flex; align-items: center; justify-content: center;
  }
  .kpi-icon-bg .icon { width: 18px; height: 18px; }
  .kpi-value {
    font-family: var(--font-serif);
    font-size: 36px; font-weight: 700; color: var(--text);
    line-height: 1; letter-spacing: -0.03em;
  }
  .kpi-unit { font-size: 16px; color: var(--text-muted); margin-left: 4px; font-weight: 400; font-family: var(--font-sans); }
  .kpi-desc { font-size: 12px; color: var(--text-soft); margin-top: var(--s-3); line-height: 1.4; }

  /* ── Section heading ──────────────────────────────────────────────────── */
  .section-head { margin: var(--s-7) 0 var(--s-4) 0; display: flex; justify-content: space-between; align-items: baseline; }
  .section-title {
    font-family: var(--font-serif);
    font-size: 24px; font-weight: 700; letter-spacing: -0.01em; color: var(--text);
  }
  .section-sub { font-size: 13px; color: var(--text-muted); }

  /* ── Charts ───────────────────────────────────────────────────────────── */
  .charts { display: grid; grid-template-columns: 1fr 1.6fr; gap: var(--s-4); }
  @media (max-width: 900px) { .charts { grid-template-columns: 1fr; } }

  .card {
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: var(--s-5);
  }
  .card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--s-4); }
  .card-title {
    font-size: 12px; font-weight: 700; letter-spacing: 0.08em;
    color: var(--text-muted); text-transform: uppercase;
    display: flex; align-items: center; gap: var(--s-2);
  }
  .card-title .icon { width: 16px; height: 16px; color: var(--pwc-orange); }
  .chart-wrap { position: relative; height: 260px; }

  /* ── Incidents list ───────────────────────────────────────────────────── */
  .date-filter {
    display: flex; align-items: center; gap: var(--s-2); flex-wrap: wrap;
  }
  .period-btn {
    height: 32px; padding: 0 var(--s-3);
    background: rgba(255,255,255,0.85);
    border: 1px solid var(--border-strong); border-radius: 6px;
    font-family: inherit; font-size: 12px; font-weight: 500;
    color: var(--text-muted); cursor: pointer;
    transition: all 120ms ease;
    backdrop-filter: blur(6px);
  }
  .period-btn:hover { background: var(--pwc-orange-bg); color: var(--text); border-color: var(--pwc-orange); }
  .period-btn.active { background: var(--pwc-orange); color: #fff; border-color: var(--pwc-orange); font-weight: 600; }
  .filter-sep { width: 1px; height: 20px; background: var(--border-strong); margin: 0 var(--s-1); }
  .date-range { display: flex; align-items: center; gap: var(--s-2); }
  .date-input {
    height: 32px; padding: 0 var(--s-3);
    background: rgba(255,255,255,0.85);
    border: 1px solid var(--border-strong); border-radius: 6px;
    font-family: inherit; font-size: 12px; color: var(--text);
    cursor: pointer; backdrop-filter: blur(6px);
    transition: border-color 120ms ease;
  }
  .date-input:focus { outline: none; border-color: var(--pwc-orange); }
  .date-range-label { font-size: 11px; color: var(--text-soft); white-space: nowrap; }
  .filter-apply {
    height: 32px; padding: 0 var(--s-3);
    background: var(--pwc-orange); color: #fff;
    border: none; border-radius: 6px;
    font-family: inherit; font-size: 12px; font-weight: 600;
    cursor: pointer; transition: background 120ms ease;
  }
  .filter-apply:hover { background: var(--pwc-orange-dark); }

  .incident { border-top: 1px solid var(--border); }
  .incident:first-child { border-top: 1px solid var(--border-strong); }
  .incident-row {
    display: grid;
    grid-template-columns: 16px 150px 200px minmax(0, 1fr) 100px 140px;
    gap: var(--s-4);
    align-items: center;
    padding: var(--s-3) var(--s-1);
    cursor: pointer;
    transition: background 120ms ease;
  }
  .incident-row:hover { background: var(--pwc-orange-bg); }
  .incident.open > .incident-row { background: var(--pwc-orange-bg); }

  .chev { color: var(--text-soft); transition: transform 160ms ease; }
  .incident.open .chev { transform: rotate(90deg); }
  .meta-time { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); }
  .meta-class { font-weight: 600; color: var(--text); display: flex; align-items: center; gap: var(--s-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .meta-pod   { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }

  .badge {
    display: inline-flex; align-items: center; justify-content: center; gap: 4px;
    height: 22px; padding: 0 var(--s-2);
    border-radius: 4px;
    font-size: 11px; font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  .badge .icon { width: 12px; height: 12px; }
  .badge-critical { color: var(--danger); background: var(--danger-bg); }
  .badge-warning  { color: var(--warn);   background: var(--warn-bg); }
  .badge-info     { color: var(--info);   background: var(--info-bg); }
  .badge-ok       { color: var(--success); background: var(--success-bg); }
  .badge-skip     { color: var(--text-muted); background: #F0F0F0; }

  /* Body (expandable detail) */
  .incident-body { display: none; padding: var(--s-5); background: var(--pwc-cream); border-top: 1px solid var(--border); }
  .incident.open > .incident-body { display: block; }
  .field { margin-bottom: var(--s-4); }
  .field:last-child { margin-bottom: 0; }
  .field-label {
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    color: var(--text-muted); text-transform: uppercase;
    margin-bottom: var(--s-2); display: flex; align-items: center; gap: var(--s-2);
  }
  .field-label .icon { width: 13px; height: 13px; color: var(--pwc-orange); }
  .field-value { font-size: 14px; color: var(--text); line-height: 1.6; }
  .runbook-step { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: var(--s-3); margin-bottom: var(--s-2); }
  .step-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 18px; height: 18px; border-radius: 50%;
    background: var(--pwc-orange); color: white;
    font-size: 10px; font-weight: 700;
  }
  .step-action { font-weight: 600; font-size: 13px; color: var(--text); display: flex; align-items: center; gap: var(--s-2); }
  .step-cmd {
    font-family: var(--font-mono); font-size: 12px;
    background: #1F1F1F; color: #E5E5E5;
    padding: var(--s-2) var(--s-3); border-radius: 4px;
    margin: var(--s-2) 0; overflow-x: auto; white-space: pre;
  }
  .step-desc { font-size: 12px; color: var(--text-muted); }
  .raw-json {
    background: #1F1F1F; color: #A6E3A1;
    padding: var(--s-3); border-radius: 6px;
    font-family: var(--font-mono); font-size: 11px;
    max-height: 320px; overflow: auto;
    white-space: pre-wrap; word-break: break-word;
  }

  .empty { text-align: center; padding: var(--s-7) var(--s-5); color: var(--text-muted); }
  .empty .icon { width: 32px; height: 32px; color: var(--text-soft); margin-bottom: var(--s-3); }

  /* En-têtes des colonnes incidents */
  .incident-header {
    display: grid;
    grid-template-columns: 16px 150px 200px minmax(0, 1fr) 100px 140px;
    gap: var(--s-4);
    align-items: center;
    padding: var(--s-3) var(--s-1);
    border-bottom: 2px solid var(--pwc-orange);
    background: rgba(220,105,0,0.04);
    border-radius: 8px 8px 0 0;
  }
  .inc-head-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  /* Responsive */
  @media (max-width: 1100px) {
    .incident-row    { grid-template-columns: 16px 130px minmax(0,1fr) 90px 140px; }
    .incident-header { grid-template-columns: 16px 130px minmax(0,1fr) 90px 140px; }
    .meta-class      { display: none; }
    .inc-head-class  { display: none; }
  }
  @media (max-width: 700px) {
    .incident-row    { grid-template-columns: 16px minmax(0,1fr) 130px; }
    .incident-header { grid-template-columns: 16px minmax(0,1fr) 130px; }
    .meta-time, .meta-pod { display: none; }
    .inc-head-time, .inc-head-pod { display: none; }
  }
</style>
</head>
<body>
<div class="layout">

  <!-- ─── SIDEBAR ────────────────────────────────────────────────────── -->
  <aside class="sidebar">
    <div class="brand">
      <img src="/static/logo.png" alt="PwC SRE Copilot" />
    </div>

    <nav class="nav">
      <a href="#" class="active"><i data-lucide="layout-dashboard" class="icon"></i>Dashboard</a>
      <a href="/audit-report"><i data-lucide="file-text" class="icon"></i>Audit Report</a>
      <a href="/docs"><i data-lucide="book-open" class="icon"></i>API Docs</a>
      <a href="/metrics"><i data-lucide="activity" class="icon"></i>Metrics</a>
      <a href="http://localhost:3000" target="_blank"><i data-lucide="bar-chart-3" class="icon"></i>Grafana</a>
      <a href="http://localhost:9090" target="_blank"><i data-lucide="search" class="icon"></i>Prometheus</a>
      <a href="http://localhost:9093" target="_blank"><i data-lucide="bell" class="icon"></i>Alertmanager</a>
      <a href="http://localhost:5678" target="_blank"><i data-lucide="workflow" class="icon"></i>n8n</a>
    </nav>
  </aside>

  <!-- ─── MAIN ───────────────────────────────────────────────────────── -->
  <main class="main">

    <!-- Hero -->
    <section class="hero">
      <div class="hero-eyebrow">Incident portfolio</div>
      <h1 class="hero-title">SRE Copilot</h1>
      <!--
      <p class="hero-subtitle">
        Visualisation dynamique des alertes Kubernetes traitées, classification IA, taux de remédiation
        automatique, MTTR mesuré et traçabilité GitOps des actions appliquées.
      </p>
      -->
      <div class="hero-bars"><span></span><span></span></div>
      <div class="hero-meta">
        <div class="hero-stack">Active mission: <b>Audit IT — Détection &amp; remédiation des incidents Kubernetes</b></div>
        <div class="hero-actions">
          <span id="last-update" class="last-update">—</span>
          <button class="btn" onclick="loadAll()">
            <i data-lucide="refresh-cw" class="icon"></i>Refresh
          </button>
          <a class="btn btn-primary" href="/audit-report">
            <i data-lucide="file-text" class="icon"></i>Audit Report
          </a>
        </div>
      </div>
    </section>

    <!-- KPI cards -->
    <section class="kpi-grid" id="kpi-grid"></section>

    <!-- Charts -->
    <div class="section-head">
      <h2 class="section-title">Statistiques</h2>
    </div>
    <section class="charts">
      <div class="card">
        <div class="card-head">
          <div class="card-title"><i data-lucide="pie-chart" class="icon"></i>Classifications</div>
        </div>
        <div class="chart-wrap" id="wrap-class"><canvas id="chart-class"></canvas></div>
      </div>
      <div class="card">
        <div class="card-head">
          <div class="card-title"><i data-lucide="bar-chart-3" class="icon"></i>Volume par jour</div>
        </div>
        <div class="chart-wrap" id="wrap-timeline"><canvas id="chart-timeline"></canvas></div>
      </div>
    </section>

    <!-- Incidents -->
    <div class="section-head" style="flex-wrap:wrap;gap:var(--s-3);align-items:center;">
      <h2 class="section-title">Incidents récents <span id="incidents-count" style="font-family:var(--font-sans);font-size:14px;font-weight:400;color:var(--text-muted);"></span></h2>
      <div class="date-filter">
        <button class="period-btn active" data-h="" onclick="setPeriod('', this)">Tout</button>
        <button class="period-btn" data-h="1"   onclick="setPeriod('1', this)">1h</button>
        <button class="period-btn" data-h="6"   onclick="setPeriod('6', this)">6h</button>
        <button class="period-btn" data-h="24"  onclick="setPeriod('24', this)">24h</button>
        <button class="period-btn" data-h="168" onclick="setPeriod('168', this)">7j</button>
        <div class="filter-sep"></div>
        <div class="date-range">
          <span class="date-range-label">Du</span>
          <input type="datetime-local" id="date-from" class="date-input">
          <span class="date-range-label">au</span>
          <input type="datetime-local" id="date-to" class="date-input">
          <button class="filter-apply" onclick="applyDateRange()">Appliquer</button>
        </div>
      </div>
    </div>
    <section class="card" style="padding:0; overflow:hidden;">
      <div class="incident-header">
        <span></span>
        <span class="inc-head-label inc-head-time">Horodatage</span>
        <span class="inc-head-label inc-head-class">Classification</span>
        <span class="inc-head-label inc-head-pod">Pod</span>
        <span class="inc-head-label">Sévérité</span>
        <span class="inc-head-label">Remédiation</span>
      </div>
      <div id="incidents-list"></div>
    </section>

  </main>
</div>

<script>
let chartClass = null, chartTimeline = null;
let allIncidents = [];

const STAT_ICONS = {
  total:'activity', remediated:'check-circle-2', rate:'percent',
  mttr:'clock', argocd:'git-branch',
};

// Lucide wrapper sécurisé — ne plante jamais si CDN lent ou indisponible
function safeCreateIcons() {
  try { if (typeof lucide !== 'undefined') lucide.createIcons(); } catch(e) {}
}
// Crée les icônes dès que le DOM est prêt, indépendamment des appels API
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(safeCreateIcons, 100);
  setTimeout(safeCreateIcons, 1200); // 2e tentative pour CDN lent
});

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
    document.getElementById('last-update').textContent = 'Mis à jour ' + new Date().toLocaleTimeString('fr-FR');
    safeCreateIcons();
  } catch (e) {
    document.getElementById('last-update').innerHTML =
      `<span style="color:#B81B1B;font-size:12px;">⚠ API indisponible — <button onclick="loadAll()" style="background:none;border:none;cursor:pointer;color:#DC6900;font-weight:600;font-size:12px;text-decoration:underline;font-family:inherit;">Réessayer</button></span>`;
    safeCreateIcons(); // les icônes s'affichent même si l'API est down
  }
}

function renderStats(s) {
  const cards = [
    { key:'total',      label:'Incidents traités',  value: s.total,           unit:'', desc:'Total cumulé depuis le démarrage de l\'agent.' },
    { key:'remediated', label:'Auto-remédiés',      value: s.auto_remediated, unit:'', desc:'Actions correctives appliquées sans intervention humaine.' },
    { key:'rate',       label:'Taux de succès',     value: s.success_rate,    unit:'%', desc:'Proportion d\'incidents résolus par l\'agent.' },
    { key:'mttr',       label:'MTTR moyen',         value: s.mttr_seconds,    unit:'s', desc:'Temps moyen de remédiation (collecte + LLM + action).' },
  ];
  document.getElementById('kpi-grid').innerHTML = cards.map(c => `
    <div class="kpi">
      <div class="kpi-head">
        <span class="kpi-label">${c.label}</span>
        <span class="kpi-icon-bg"><i data-lucide="${STAT_ICONS[c.key]}" class="icon"></i></span>
      </div>
      <div class="kpi-value">${c.value}<span class="kpi-unit">${c.unit}</span></div>
      <div class="kpi-desc">${c.desc}</div>
    </div>
  `).join('');
}

// PwC-aligned palette : orange dominant + neutrals
const PALETTE = ['#DC6900','#B85A00','#8B4513','#D49B6E','#7A8B99','#4A6075','#2D7A3E','#B81B1B'];

function renderClass(data) {
  const labels = Object.keys(data); const values = Object.values(data);
  const wrap = document.getElementById('wrap-class');
  if (labels.length === 0) { wrap.innerHTML = '<div class="empty"><i data-lucide="pie-chart" class="icon"></i><p>Pas encore de données</p></div>'; safeCreateIcons(); return; }
  if (!wrap.querySelector('canvas')) wrap.innerHTML = '<canvas id="chart-class"></canvas>';
  if (chartClass) chartClass.destroy();
  chartClass = new Chart(document.getElementById('chart-class'), {
    type: 'doughnut',
    data: { labels, datasets: [{
   data: values,
   backgroundColor: PALETTE,
   borderWidth: 2,
   borderColor: '#ffffff',
   hoverOffset: 22,
   spacing: 2
}] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '64%', animation: {
   duration: 1200,
   easing: 'easeOutQuart'
},
      plugins: { legend: {
   position: 'right',
   labels: {
      usePointStyle: true,
      pointStyle: 'circle',
      padding: 20,
      color: '#444',
      font: {
         family: 'Inter',
         size: 12,
         weight: '500'
      }
   }
} }
    }
  });
}

function renderTimeline(data) {
  const labels = Object.keys(data); const values = Object.values(data);
  const wrap = document.getElementById('wrap-timeline');
  if (labels.length === 0) { wrap.innerHTML = '<div class="empty"><i data-lucide="bar-chart-3" class="icon"></i><p>Pas encore de données</p></div>'; safeCreateIcons(); return; }
  if (!wrap.querySelector('canvas')) wrap.innerHTML = '<canvas id="chart-timeline"></canvas>';
  if (chartTimeline) chartTimeline.destroy();
  chartTimeline = new Chart(document.getElementById('chart-timeline'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Incidents', data: values, backgroundColor: '#DC6900', borderRadius: 4, maxBarThickness: 32 }] },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#6B6B6B', font: { size: 11, family:'Inter' } } },
        y: { beginAtZero: true, ticks: { stepSize: 1, precision: 0, color: '#6B6B6B', font: { size: 11, family:'Inter' } }, grid: { color: '#F0F0F0' } }
      }
    }
  });
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function severityIcon(sev) {
  const s = (sev||'').toLowerCase();
  if (s === 'critical') return 'alert-octagon';
  if (s === 'warning')  return 'alert-triangle';
  return 'info';
}

let activePeriodHours = null; // null = tout
let customFrom = null, customTo = null;

function setPeriod(h, btn) {
  activePeriodHours = h === '' ? null : parseInt(h, 10);
  customFrom = null; customTo = null;
  document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('date-from').value = '';
  document.getElementById('date-to').value = '';
  renderFiltered();
}

function applyDateRange() {
  const f = document.getElementById('date-from').value;
  const t = document.getElementById('date-to').value;
  if (!f && !t) return;
  customFrom = f ? new Date(f) : null;
  customTo   = t ? new Date(t) : null;
  activePeriodHours = null;
  document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
  renderFiltered();
}

function renderFiltered() {
  let filtered = allIncidents;
  if (activePeriodHours) {
    const cutoff = new Date(Date.now() - activePeriodHours * 3600000);
    filtered = filtered.filter(i => i.timestamp && new Date(i.timestamp) >= cutoff);
  } else if (customFrom || customTo) {
    filtered = filtered.filter(i => {
      if (!i.timestamp) return false;
      const d = new Date(i.timestamp);
      if (customFrom && d < customFrom) return false;
      if (customTo   && d > customTo)   return false;
      return true;
    });
  }
  renderIncidents(filtered, allIncidents.length);
  safeCreateIcons();
}

function renderIncidents(items, total) {
  document.getElementById('incidents-count').textContent = ` · ${items.length} sur ${total}`;
  const list = document.getElementById('incidents-list');
  if (items.length === 0) {
    list.innerHTML = total === 0
      ? `<div class="empty"><i data-lucide="inbox" class="icon"></i><p>Aucun incident traité pour le moment.</p></div>`
      : `<div class="empty"><i data-lucide="search-x" class="icon"></i><p>Aucun résultat pour cette recherche.</p></div>`;
    return;
  }
  list.innerHTML = items.map((i, idx) => {
    const sev = (i.severity||'info').toLowerCase();
    const sevIcon = severityIcon(sev);
    const time = i.timestamp ? new Date(i.timestamp).toLocaleString('fr-FR') : '—';
    const podFull = `${i.namespace||'?'}/${i.pod||'?'}`;
    const remediated = i.auto_remediation_applied
      ? `<span class="badge badge-ok"><i data-lucide="check" class="icon"></i>Remédié</span>`
      : `<span class="badge badge-skip"><i data-lucide="minus" class="icon"></i>Non appliqué</span>`;
    const runbookHtml = (i.runbook||[]).map(s => `
      <div class="runbook-step">
        <div class="step-action"><span class="step-num">${escapeHtml(s.order)}</span>${escapeHtml(s.action)}</div>
        ${s.command ? `<div class="step-cmd">${escapeHtml(s.command)}</div>` : ''}
        <div class="step-desc">${escapeHtml(s.description)}</div>
      </div>`).join('');
    return `
      <div class="incident" id="inc-${idx}">
        <div class="incident-row" onclick="document.getElementById('inc-${idx}').classList.toggle('open'); safeCreateIcons();">
          <i data-lucide="chevron-right" class="icon chev"></i>
          <span class="meta-time" title="${escapeHtml(i.timestamp||'')}">${time}</span>
          <span class="meta-class"><i data-lucide="${sevIcon}" class="icon" style="width:14px;height:14px;"></i>${escapeHtml(i.classification)}</span>
          <span class="meta-pod" title="${escapeHtml(podFull)}">${escapeHtml(podFull)}</span>
          <span class="badge badge-${sev}">${escapeHtml(i.severity)}</span>
          ${remediated}
        </div>
        <div class="incident-body">
          <div class="field"><div class="field-label"><i data-lucide="tag" class="icon"></i>Alert name</div><div class="field-value">${escapeHtml(i.alert_name)}</div></div>
          <div class="field"><div class="field-label"><i data-lucide="file-text" class="icon"></i>Root cause</div><div class="field-value">${escapeHtml(i.root_cause)}</div></div>
          <div class="field"><div class="field-label"><i data-lucide="list-checks" class="icon"></i>Runbook · ${(i.runbook||[]).length} étapes</div><div class="field-value">${runbookHtml}</div></div>
          ${i.remediation_details ? `<div class="field"><div class="field-label"><i data-lucide="wrench" class="icon"></i>Remédiation</div><div class="field-value">${escapeHtml(i.remediation_details)}</div></div>` : ''}
          <div class="field">
            <div class="field-label"><i data-lucide="gauge" class="icon"></i>Métriques</div>
            <div class="field-value">Durée: <b>${i.duration_seconds||'?'}s</b> · Git: <b>${escapeHtml(i.git_pr_url||'aucun')}</b> · ArgoCD: <b>${i.argocd_sync_triggered ? 'sync ✓' : 'non'}</b></div>
          </div>
          <div class="field"><div class="field-label"><i data-lucide="code" class="icon"></i>Payload JSON</div><pre class="raw-json">${escapeHtml(JSON.stringify(i, null, 2))}</pre></div>
        </div>
      </div>`;
  }).join('');
}

loadAll();
setInterval(loadAll, 30000);
window.addEventListener('resize', () => {
  if (chartClass)    chartClass.resize();
  if (chartTimeline) chartTimeline.resize();
});
</script>
</body>
</html>
"""


# ════════════════════════════════════════════════════════════════════════════
# AUDIT REPORT — Rapport imprimable façon PwC (Ctrl+P → Save as PDF)
# ════════════════════════════════════════════════════════════════════════════

AUDIT_REPORT_HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Rapport d'audit — SRE Copilot</title>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,700;1,8..60,400&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
  --orange: #FF5A00;
  --orange-dark: #E85D04;
  --orange-light: #FFF1E8;

  --text: #111111;
  --text-muted: #666666;

  --border: #E7DCCF;

  --page-bg: #FFF9F5;

  --font-serif: 'Source Serif 4', Georgia, serif;
  --font-sans: 'Inter', sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: var(--font-sans);
    background: #DEDAD5;
    color: var(--text);
    font-size: 13px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }

  /* ── Page ─────────────────────────────────────────────────────────── */
  .page{
  max-width:794px;
  margin:28px auto;
  background: #FFFFFF;
  position:relative;
  overflow:hidden;
  box-shadow: 0 10px 30px rgba(0,0,0,.08);
}

.page::before{
  content:"";
  position:absolute;
  inset:0;
  pointer-events:none;
}
  @media print {
    body { background: white !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .page {
      margin: 0 !important;
      max-width: none !important;
      box-shadow: none !important;
      overflow: visible !important;
    }
    .page::before { display: none !important; }
    .no-print { display: none !important; }
    .page-break { page-break-after: always; break-after: page; }
  }

  /* ══════════════════════════════════════
     PAGE DE COUVERTURE
  ══════════════════════════════════════ */
  .page-cover {
    min-height: 1123px;
    position: relative;
    /* Dégradé pêche exact comme le PDF PwC : coin haut-droit orange clair, reste blanc crème */
    background:
      radial-gradient(ellipse 70% 60% at 100% 0%, rgba(255,200,160,0.55) 0%, rgba(255,220,190,0.3) 40%, transparent 70%),
      radial-gradient(ellipse 50% 40% at 100% 100%, rgba(255,180,140,0.15) 0%, transparent 50%),
      linear-gradient(160deg, #FFF8F4 0%, #FFF5EE 40%, #FFFAF7 70%, #FFFFFF 100%);
  }

  .cover-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 44px 56px 0 56px;
    position: relative;
    z-index: 2;
  }
  .cover-logo { width: 88px; height: auto; display: block; }
  .cover-date { font-size: 11px; color: var(--text-muted); margin-top: 6px; }

  .cover-body {
    padding: 120px 56px 0 56px;
    position: relative;
    z-index: 2;
  }
  .cover-h1 {
    font-family: var(--font-serif);
    font-size: 80px;
    font-weight: 700;
    line-height: 0.92;
    letter-spacing: -0.03em;
    color: #000;
    margin-bottom: 28px;
  }
  .cover-sub {
    font-family: var(--font-sans);
    font-size: 16px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.4;
  }

  /* Deux parallelogrammes bas — positionnés exactement comme le PDF PwC */
  .cover-shapes {
    position: absolute;
    left: 0;
    right: 0;
    /* PDF: formes à ~57% de la hauteur de page (1123px * 0.57 = 640px) */
    bottom: 220px;
    height: 160px;
    z-index: 1;
  }
  /* Forme gauche (foncée, bordeaux-orangé) — déborde à gauche */
  .shape-back {
    position: absolute;
    width: 420px;
    height: 105px;
    background: #C44000;
    transform: skewX(-20deg);
    left: -40px;
    top: 45px;
  }
  /* Forme droite (orange vif) — décalée à droite, devant */
  .shape-front {
    position: absolute;
    width: 420px;
    height: 105px;
    background: #E85D04;
    transform: skewX(-20deg);
    left: 310px;
    top: 0;
  }
  /* ══════════════════════════════════════
     SOMMAIRE
  ══════════════════════════════════════ */
  .page-toc { min-height: 1123px; padding: 56px 0 56px 0; }

  .toc-h{
  font-family:var(--font-serif);

  font-size:64px;
  font-weight:700;

  padding: 0 56px;
  margin-bottom:60px;
}

  .toc-list { list-style: none; padding: 0 56px; counter-reset: toc; }
  .toc-list li {
    display: flex;
    align-items: baseline;
    gap: 16px;
    counter-increment: toc;
    padding: 14px 0;
    border-bottom: 1px solid var(--border);
    font-family: var(--font-serif);
    font-size: 20px;
    color: var(--text);
  }
  .toc-list li::before {
    content: "0" counter(toc);
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 700;
    color: var(--orange);
    min-width: 26px;
    flex-shrink: 0;
  }

  .toc-meta {
    margin: 48px 56px 0 56px;
    border-top: 2px solid var(--orange);
    padding-top: 18px;
  }
  .toc-meta table { border-collapse: collapse; font-size: 12px; width: 100%; }
  .toc-meta thead th {
    padding: 8px 12px 8px 0;
    font-size: 9px; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--orange-dark);
    border-bottom: 1px solid var(--border);
    background: transparent;
  }
  .tmc-l { color: var(--text-muted); padding: 5px 20px 5px 0; font-weight: 500; width: 150px; vertical-align: top; }
  .tmc-r { color: var(--text); padding: 5px 0; font-family: var(--font-mono); font-size: 11px; }

  /* ══════════════════════════════════════
     PAGES CONTENU
  ══════════════════════════════════════ */
  .page-content { padding-bottom: 64px; }

  /* Breadcrumb discret en haut */
  .page-bread {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #999;
    padding: 22px 56px 0 56px;
    margin-bottom: 32px;
  }

  /* Période */
  .period-line {
    padding: 0 56px;
    margin-bottom: 40px;
    font-size: 12px;
    color: var(--text-muted);
  }
  .period-line strong { color: var(--text); }

  /* Sections */
  .section { padding: 0 56px; margin-bottom: 52px; }

  .section-h {
    font-family: var(--font-serif);
    font-size: 28px;
    font-weight: 700;
    color: var(--text);
    display: flex;
    align-items: baseline;
    gap: 14px;
    margin-bottom: 6px;
    line-height: 1.2;
  }
  .sec-num {
    font-family: var(--font-sans);
    font-size: 13px;
    font-weight: 700;
    color: var(--orange);
    flex-shrink: 0;
  }
  .section-rule {
    height: 1px;
    background: var(--border);
    margin-bottom: 24px;
  }

  .narrative { font-size: 14px; line-height: 1.75; color: var(--text); margin-bottom: 16px; }

  /* Risk */
  .risk-banner {
    display: flex; align-items: flex-start; gap: 12px;
    padding: 14px 16px; margin-top: 12px;
    border-left: 4px solid;
  }
  .risk-low    { background: #EEF7EF; border-color: #2D7A3E; color: #2D7A3E; }
  .risk-medium { background: #FFF4E5; border-color: #B86E00; color: #B86E00; }
  .risk-high   { background: #FBF0F0; border-color: #B81B1B; color: #B81B1B; }
  .risk-banner .icon { width: 18px; height: 18px; flex-shrink: 0; margin-top: 2px; }
  .risk-label { font-weight: 700; font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; }
  .risk-desc  { font-size: 13px; color: var(--text); margin-top: 3px; line-height: 1.5; }

  /* KPIs — blocs colorés (classes explicites, fiables sur contenu dynamique) */
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3px; margin: 4px 0; }
  .kpi-box  { padding: 20px 16px; color: white; }
  .kpi-1    { background: #1E6080; }
  .kpi-2    { background: #8B1F1F; }
  .kpi-3    { background: #C44A00; }
  .kpi-4    { background: #E85D04; }
  .kpi-label { font-size: 10px; font-weight: 500; opacity: 0.82; margin-bottom: 10px; letter-spacing: 0.04em; }
  .kpi-value { font-family: var(--font-serif); font-size: 38px; font-weight: 700; line-height: 1; }
  .kpi-unit  { font-size: 16px; font-weight: 400; opacity: 0.75; margin-left: 2px; }
.kpi {
    background: rgba(255,255,255,.92);
    border: 1px solid #EAEAEA;
    border-radius: 14px;
    padding: 24px;
    transition: all .25s ease;
}

.kpi:hover{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,.06);
}
  /* Tables */
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th {
    padding: 10px 12px; text-align: left;
    font-size: 10px; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--text);
    border-bottom: 2px solid var(--orange);
    background: rgba(232,93,4,0.05);
  }
  td { padding: 9px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
  .mono { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }
  tr:nth-child(even) td { background: rgba(0,0,0,0.018); }

  /* Badges */
  .badge { display: inline-block; padding: 2px 8px; font-size: 10px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }
  .badge-ok       { background: #E8F5EC; color: #2D7A3E; }
  .badge-fail     { background: #F0F0F0; color: #888; }
  .badge-critical { background: #FBEAEA; color: #B81B1B; }
  .badge-warning  { background: #FFF4E5; color: #B86E00; }
  .badge-info     { background: #E8F0F7; color: #1F5680; }

  /* Recommandations */
  .recs { list-style: none; padding: 0; }
  .recs li {
    background: rgba(232,93,4,0.04);
    border-left: 3px solid var(--orange);
    border-radius: 0;
    padding: 12px 16px 12px 44px;
    position: relative;

  margin-bottom:12px;
}
  .recs li::before {
    content: "→";
    position: absolute;
    left: 14px;
    color: var(--orange);
    font-weight: 700;
  }

  /* Méthodologie */
  .method-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
  .method-box {
    border: 1px solid var(--border);
    border-top: 3px solid var(--orange);
    padding: 16px;
    font-size: 12px;
    line-height: 1.65;
  }
  .method-box .label { font-size: 9px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--orange-dark); margin-bottom: 8px; }

  /* ══════════════════════════════════════
     PAGE BACK COVER
  ══════════════════════════════════════ */
  .page-back {
    min-height: 1123px;
    display: flex;
    flex-direction: column;
  }
  .page-back .cover-top { padding: 44px 56px 0 56px; }

  .back-shapes {
    flex: 1;
    position: relative;
  }
  .back-shapes .shape-back {
    position: absolute;
    width: 540px;
    height: 102px;
    background: var(--orange-dark);
    transform: skewX(-18deg);
    left: -70px;
    bottom: 180px;
  }
  .back-shapes .shape-front {
    position: absolute;
    width: 620px;
    height: 102px;
    background: var(--orange);
    transform: skewX(-18deg);
    left: 160px;
    bottom: 264px;
  }

  .back-copy {
    padding: 24px 56px;
    font-size: 10px;
    color: var(--text-muted);
    line-height: 1.7;
    border-top: 1px solid var(--border);
  }

  /* ── Floating controls ── */
  .controls { position: fixed; top: 20px; right: 28px; display: flex; gap: 10px; z-index: 100; }
  .ctrl-btn {
    display: inline-flex; align-items: center; gap: 6px;
    height: 36px; padding: 0 16px;
    background: white; border: 1px solid #C8C8C8; border-radius: 6px;
    font-family: inherit; font-size: 13px; font-weight: 500; color: var(--text);
    cursor: pointer; text-decoration: none; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }
  .ctrl-btn:hover { background: #FFF0E6; border-color: var(--orange); }
  .ctrl-btn .icon { width: 14px; height: 14px; stroke-width: 2; }
  .ctrl-btn.primary { background: var(--orange); color: white; border-color: var(--orange); }
  .ctrl-btn.primary:hover { background: var(--orange-dark); }
  .period-selector { display: inline-flex; gap: 3px; background: white; border: 1px solid #C8C8C8; border-radius: 6px; padding: 2px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  .period-selector button { background: transparent; border: 0; padding: 6px 12px; cursor: pointer; font-size: 12px; font-weight: 500; color: #888; border-radius: 4px; font-family: inherit; }
  .period-selector button.active { background: var(--orange); color: white; font-weight: 700; }

  /* Export dropdown */
  .export-wrap { position: relative; }
  .export-menu {
    display: none; position: absolute; top: calc(100% + 6px); right: 0;
    background: white; border: 1px solid #E0E0E0; border-radius: 8px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.14); min-width: 268px;
    z-index: 150; overflow: hidden;
  }
  .export-menu.open { display: block; }
  .export-item {
    display: flex; align-items: center; gap: 12px;
    padding: 11px 16px; text-decoration: none; color: inherit;
    border-bottom: 1px solid #F0F0F0; transition: background 0.13s;
  }
  .export-item:last-child { border-bottom: none; }
  .export-item:hover { background: #FFF5EC; }
  .export-item .icon { width: 18px; height: 18px; stroke-width: 1.5; color: var(--orange); flex-shrink: 0; }
  .export-item strong { display: block; font-size: 13px; font-weight: 600; color: #1A1A1A; }
  .export-item span { display: block; font-size: 11px; color: #888; margin-top: 1px; }
</style>
</head>
<body>

<!-- Floating controls (screen only) -->
<div class="controls no-print">
  <div class="period-selector">
    <button id="p24" class="active" onclick="setPeriod(24)">24h</button>
    <button id="p48" onclick="setPeriod(48)">48h</button>
    <button id="p168" onclick="setPeriod(168)">7j</button>
  </div>
  <a class="ctrl-btn" href="/dashboard"><i data-lucide="layout-dashboard" class="icon"></i>Retour</a>
  <div class="export-wrap">
    <button class="ctrl-btn primary" onclick="toggleExport(event)">
      <i data-lucide="download" class="icon"></i>Exporter
    </button>
    <div class="export-menu" id="export-menu">
      <a class="export-item" id="dl-pptx" href="/export/pptx?hours=24" download>
        <i data-lucide="presentation" class="icon"></i>
        <div><strong>PowerPoint</strong><span>Présentation modifiable (.pptx)</span></div>
      </a>
      <a class="export-item" id="dl-pdf" href="/export/pdf?hours=24" download>
        <i data-lucide="file-text" class="icon"></i>
        <div><strong>PDF</strong><span>Copie de révision fixe (.pdf)</span></div>
      </a>
      <a class="export-item" id="dl-docx" href="/export/docx?hours=24" download>
        <i data-lucide="file" class="icon"></i>
        <div><strong>Word</strong><span>Document modifiable (.docx)</span></div>
      </a>
    </div>
  </div>
</div>

<!-- ══════════════════════════
     PAGE 1 — COUVERTURE
══════════════════════════ -->
<div class="page page-cover page-break">
  <div class="cover-top">
    <img src="/static/logo.png" alt="PwC" class="cover-logo">
    <span class="cover-date" id="cover-date">—</span>
  </div>
  <div class="cover-body">
    <h1 class="cover-h1">Rapport<br>D'audit</h1>
    <p class="cover-sub" id="period-eyebrow">Alertes Kubernetes &amp; remédiation SRE</p>
  </div>
  <div class="cover-shapes">
    <div class="shape-back"></div>
    <div class="shape-front"></div>
  </div>
</div>

<!-- ══════════════════════════
     PAGE 2 — SOMMAIRE
══════════════════════════ -->
<div class="page page-toc page-break">
  <h2 class="toc-h">Sommaire</h2>
  <ol class="toc-list">
    <li>Résumé exécutif</li>
    <li>Indicateurs clés de performance</li>
    <li>Répartition par classification</li>
    <li>Journal détaillé des incidents</li>
  </ol>
  <div class="toc-meta">
    <table>
      <thead>
        <tr>
          <th class="tmc-l">Information</th>
          <th class="tmc-r">Détail</th>
        </tr>
      </thead>
      <tbody>
        <tr><td class="tmc-l">Période</td><td class="tmc-r" id="period-range-cover">—</td></tr>
        <tr><td class="tmc-l">Généré le</td><td class="tmc-r" id="generated-at">—</td></tr>
        <tr><td class="tmc-l">Classification</td><td class="tmc-r">Confidentiel · Usage interne</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- ══════════════════════════
     PAGES CONTENU
══════════════════════════ -->
<div class="page page-content page-break">
  <div class="page-bread">Rapport d'audit — Alertes Kubernetes &amp; remédiation SRE</div>

  <div class="period-line">Période analysée : <strong id="period-range">—</strong></div>

  <!-- 01 -->
  <div class="section">
    <h2 class="section-h"><span class="sec-num">01</span> Résumé exécutif</h2>
    <div class="section-rule"></div>
    <p class="narrative" id="narrative">Chargement…</p>
    <div id="risk-banner-mount"></div>
  </div>

  <!-- 02 -->
  <div class="section">
    <h2 class="section-h"><span class="sec-num">02</span> Indicateurs clés de performance</h2>
    <div class="section-rule"></div>
    <div class="kpi-grid" id="kpi-grid"></div>
  </div>

  <!-- 03 -->
  <div class="section">
    <h2 class="section-h"><span class="sec-num">03</span> Répartition par classification</h2>
    <div class="section-rule"></div>
    <div id="classifications-mount"></div>
  </div>

  <!-- 04 -->
  <div class="section">
    <h2 class="section-h"><span class="sec-num">04</span> Journal détaillé des incidents</h2>
    <div class="section-rule"></div>
    <div id="incidents-mount"></div>
  </div>


</div>

<script>
let currentPeriod = 24;

function setPeriod(hours) {
  currentPeriod = hours;
  document.querySelectorAll('.period-selector button').forEach(b => b.classList.remove('active'));
  document.getElementById(`p${hours}`).classList.add('active');
  const label = hours >= 168 ? `Alertes Kubernetes & remédiation SRE — ${Math.round(hours/24)} jours` : `Alertes Kubernetes & remédiation SRE — ${hours}h`;
  document.getElementById('period-eyebrow').textContent = label;
  updateExportLinks(hours);
  load();
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function load() {
  const r = await fetch(`/api/audit-report?hours=${currentPeriod}`);
  const data = await r.json();
  render(data);
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function render(data) {
  const start = new Date(data.period_start);
  const end   = new Date(data.period_end);
  const fmt = d => d.toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' });
  const fmtShort = d => d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
  const rangeText = `${fmt(start)}  →  ${fmt(end)}`;
  document.getElementById('period-range').textContent = rangeText;
  document.getElementById('period-range-cover').textContent = `${fmtShort(start)} → ${fmtShort(end)}`;
  document.getElementById('cover-date').textContent = fmtShort(end);

  // Narrative
  document.getElementById('narrative').textContent = data.summary.narrative;

  // Risk banner
  const risk = data.summary.risk_level;
  const riskMap = {
    low:    { icon: 'check-circle-2', label: 'Niveau de risque · faible', desc: "Aucune action immédiate requise. La plateforme opère dans les standards attendus." },
    medium: { icon: 'alert-triangle', label: 'Niveau de risque · modéré', desc: "Quelques signaux nécessitent attention. Voir les recommandations en section 05." },
    high:   { icon: 'alert-octagon',  label: 'Niveau de risque · élevé', desc: "Plusieurs anomalies détectées. Une revue manuelle est recommandée rapidement." },
  };
  const rm = riskMap[risk] || riskMap.low;
  document.getElementById('risk-banner-mount').innerHTML = `
    <div class="risk-banner risk-${risk}">
      <i data-lucide="${rm.icon}" class="icon"></i>
      <div>
        <div class="risk-label">${rm.label}</div>
        <div class="risk-desc">${rm.desc}</div>
      </div>
    </div>`;

  // KPIs
  const k = data.summary.kpis;
  document.getElementById('kpi-grid').innerHTML = `
    <div class="kpi-box kpi-1"><div class="kpi-label">Total incidents</div><div class="kpi-value">${k.total}</div></div>
    <div class="kpi-box kpi-2"><div class="kpi-label">Auto-remédiés</div><div class="kpi-value">${k.auto_remediated}</div></div>
    <div class="kpi-box kpi-3"><div class="kpi-label">Taux de succès</div><div class="kpi-value">${k.success_rate}<span class="kpi-unit">%</span></div></div>
    <div class="kpi-box kpi-4"><div class="kpi-label">MTTR moyen</div><div class="kpi-value">${Math.round(k.mttr_seconds)}<span class="kpi-unit">s</span></div></div>
  `;

  // Classifications table
  const classEntries = Object.entries(data.summary.classifications).sort((a,b) => b[1]-a[1]);
  if (classEntries.length === 0) {
    document.getElementById('classifications-mount').innerHTML =
      '<p style="font-size:13px;color:var(--text-muted);font-style:italic;">Aucune classification sur la période.</p>';
  } else {
    const total = k.total || 1;
    document.getElementById('classifications-mount').innerHTML = `
      <table>
        <thead><tr><th>Classification</th><th>Occurrences</th><th>Part</th><th>Action automatique</th></tr></thead>
        <tbody>
          ${classEntries.map(([cls, count]) => {
            const pct = ((count/total)*100).toFixed(1);
            const fixMap = { CrashLoopBackOff: 'scale_to_zero', OOMKilled: 'restart', ConfigError: 'restart', ImagePullBackOff: 'aucune', NetworkError: 'aucune', ResourceExhausted: 'aucune', Unknown: 'aucune' };
            return `<tr><td><strong>${escapeHtml(cls)}</strong></td><td>${count}</td><td>${pct}%</td><td class="mono">${fixMap[cls] || '-'}</td></tr>`;
          }).join('')}
        </tbody>
      </table>`;
  }

  // Incidents table
  if (data.incidents.length === 0) {
    document.getElementById('incidents-mount').innerHTML =
      '<p style="font-size:13px;color:var(--text-muted);font-style:italic;">Aucun incident sur la période.</p>';
  } else {
    document.getElementById('incidents-mount').innerHTML = `
      <table>
        <thead><tr><th style="width:130px;">Horodatage</th><th>Classification</th><th>Pod</th><th style="width:80px;">Sévérité</th><th style="width:110px;">Remédiation</th><th style="width:60px;">Durée</th></tr></thead>
        <tbody>
          ${data.incidents.slice().reverse().map(i => {
            const sev = (i.severity||'info').toLowerCase();
            const time = i.timestamp ? new Date(i.timestamp).toLocaleString('fr-FR', { dateStyle:'short', timeStyle:'medium' }) : '—';
            const remediated = i.auto_remediation_applied
              ? '<span class="badge badge-ok">Remédié</span>'
              : '<span class="badge badge-fail">Non appliqué</span>';
            return `<tr>
              <td class="mono">${time}</td>
              <td><strong>${escapeHtml(i.classification)}</strong></td>
              <td class="mono">${escapeHtml((i.namespace||'?') + '/' + (i.pod||'?'))}</td>
              <td><span class="badge badge-${sev}">${escapeHtml(i.severity)}</span></td>
              <td>${remediated}</td>
              <td class="mono">${i.duration_seconds ? Math.round(i.duration_seconds) + 's' : '—'}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>`;
  }

  // Footer date
  document.getElementById('generated-at').textContent = new Date(data.generated_at).toLocaleString('fr-FR');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function toggleExport(e) {
  e.stopPropagation();
  document.getElementById('export-menu').classList.toggle('open');
}
document.addEventListener('click', function() {
  document.getElementById('export-menu').classList.remove('open');
});
function updateExportLinks(hours) {
  ['pptx', 'pdf', 'docx'].forEach(fmt => {
    const el = document.getElementById('dl-' + fmt);
    if (el) el.href = '/export/' + fmt + '?hours=' + hours;
  });
}

load();
</script>
</body>
</html>
"""
