"""
Generates rapport/figures/roadmap.png (PNG version of the project roadmap).
Mirrors the design of roadmap.svg using Pillow for portability.

Run: python scripts/generate_roadmap.py
"""
from PIL import Image, ImageDraw, ImageFont
import os

# ── Canvas ─────────────────────────────────────────────────────────────────────
W, H = 1400, 970
BG = (244, 246, 250)

# ── Palette (matches SVG) ──────────────────────────────────────────────────────
NAVY        = (31, 56, 100)
TEAL        = (0, 112, 127)
GREEN_DARK  = (45, 80, 22)
GREEN_BG    = (226, 239, 218)
ORANGE      = (197, 80, 12)
ORANGE_BG   = (255, 228, 208)
TEXT        = (44, 44, 44)
MUTED       = (110, 123, 139)
BORDER      = (214, 220, 228)
WHITE       = (255, 255, 255)

# ── Fonts (Windows Fonts) ──────────────────────────────────────────────────────
WIN_FONTS = "C:/Windows/Fonts"
def font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(f"{WIN_FONTS}/{name}", size)

F_TITLE       = font(28, bold=True)
F_SUBTITLE    = font(12)
F_HUGE        = font(44, bold=True)
F_PILL        = font(11, bold=True)
F_NODE        = font(11, bold=True)
F_NODE_NUM    = font(18, bold=True)
F_NODE_NUM_SM = font(14, bold=True)
F_MICRO       = font(10, bold=True)
F_LABEL       = font(10, bold=True)
F_HEAD        = font(18, bold=True)
F_DESC        = font(11)
F_BODY        = font(11)
F_TOOL        = font(11)
F_PCT         = font(11, bold=True)
F_PCT_NORM    = font(11)
F_LEG         = font(12)
F_NEXT_LBL    = font(10, bold=True)
F_NEXT_TXT    = font(12, bold=True)


# ── Drawing helpers ────────────────────────────────────────────────────────────

def rrect(d, x, y, w, h, r, fill=None, outline=None, width=1):
    d.rounded_rectangle((x, y, x + w, y + h), radius=r, fill=fill, outline=outline, width=width)

def text_anchor(d, x, y, txt, fnt, fill, anchor="lt"):
    """anchor: lt=left-top, lm=left-middle, mm=middle-middle, rm=right-middle, etc."""
    d.text((x, y), txt, font=fnt, fill=fill, anchor=anchor)

def gradient_rect(img, x, y, w, h, c1, c2):
    """Vertical gradient (top to bottom)."""
    for i in range(h):
        ratio = i / max(h - 1, 1)
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        ImageDraw.Draw(img).line([(x, y + i), (x + w, y + i)], fill=(r, g, b))

def horizontal_gradient(img, x, y, w, h, c1, c2):
    """Horizontal gradient (left to right)."""
    for i in range(w):
        ratio = i / max(w - 1, 1)
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        ImageDraw.Draw(img).line([(x + i, y), (x + i, y + h)], fill=(r, g, b))

def draw_card_top(img, x, y, w, color_top, color_bottom):
    """Draw the colored top of a card (54px tall with rounded top corners)."""
    # Use rounded rectangle then overlay
    d = ImageDraw.Draw(img)
    # Draw a rounded rect for header
    rrect(d, x, y, w, 54, 10, fill=color_top)
    # Cover bottom corners (square them off)
    d.rectangle((x, y + 44, x + w, y + 54), fill=color_top)


# ── Card rendering ─────────────────────────────────────────────────────────────

def draw_card(img, x, y, *, status, num, title1, title2, description, items, tools, pct, time_est, highlight=False):
    """Draw one mission card."""
    d = ImageDraw.Draw(img)
    W_CARD, H_CARD = 256, 540

    # Shadow (slight offset rect behind)
    rrect(d, x + 2, y + 4, W_CARD, H_CARD, 10, fill=(0, 0, 0, 0))

    # Card body
    outline = NAVY if highlight else BORDER
    width   = 2    if highlight else 1
    rrect(d, x, y, W_CARD, H_CARD, 10, fill=WHITE, outline=outline, width=width)

    # Colored top bar (with rounded top only)
    bar_color_top    = GREEN_DARK if status == "done" else ORANGE
    bar_color_bottom = (45, 80, 22) if status == "done" else (160, 69, 9)
    draw_card_top(img, x, y, W_CARD, bar_color_top, bar_color_bottom)

    # Status text inside bar
    text_anchor(d, x + W_CARD // 2, y + 12, "STATUT", F_MICRO, WHITE, anchor="mt")
    status_label = "✓ COMPLETE" if status == "done" else "⏳ À FAIRE"
    text_anchor(d, x + W_CARD // 2, y + 28, status_label, F_NODE, WHITE, anchor="mt")

    # Mission label
    label_color = MUTED if status == "done" else ORANGE
    text_anchor(d, x + 20, y + 75, f"MISSION {num}", F_MICRO, label_color)

    # Mission title (2 lines)
    text_anchor(d, x + 20, y + 100, title1, F_HEAD, NAVY)
    text_anchor(d, x + 20, y + 122, title2, F_HEAD, NAVY)

    # Description (2 lines max)
    for i, line in enumerate(description[:2]):
        text_anchor(d, x + 20, y + 152 + i * 16, line, F_DESC, MUTED)

    # Items section
    items_label = "COMPOSANTS" if status == "done" else "À RÉALISER"
    text_anchor(d, x + 20, y + 200, items_label, F_LABEL, MUTED)

    bullet = "✓" if status == "done" else "○"
    for i, item in enumerate(items[:7]):
        text_anchor(d, x + 20, y + 222 + i * 18, f"{bullet} {item}", F_BODY, TEXT)

    # Tools section
    text_anchor(d, x + 20, y + 370, "OUTILS", F_LABEL, MUTED)
    for i, tool_line in enumerate(tools[:2]):
        text_anchor(d, x + 20, y + 390 + i * 15, tool_line, F_TOOL, TEXT)

    # Progress section
    progress_label = "AVANCEMENT" if status == "done" else "ESTIMATION"
    text_anchor(d, x + 20, y + 450, progress_label, F_LABEL, MUTED)

    # Bar background + fill
    bar_bg   = GREEN_BG  if status == "done" else ORANGE_BG
    bar_fill = GREEN_DARK if status == "done" else ORANGE
    rrect(d, x + 20, y + 470, 216, 8, 4, fill=bar_bg)
    fill_w = int(216 * (pct / 100))
    if fill_w > 0:
        rrect(d, x + 20, y + 470, fill_w, 8, 4, fill=bar_fill)

    # Pct text + time est
    pct_color = GREEN_DARK if status == "done" else ORANGE
    text_anchor(d, x + 20, y + 492, f"{pct}%", F_PCT, pct_color)
    text_anchor(d, x + W_CARD - 20, y + 492, time_est, F_PCT_NORM, MUTED, anchor="rt")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # ── Header bar with gradient ───────────────────────────────────────────────
    # Slight rounding effect by drawing rounded rect + gradient inside via separate image
    # Simpler: draw gradient rect, then overlay with rounded rect outline
    horizontal_gradient(img, 40, 30, 1320, 100, NAVY, TEAL)
    # Mask corners with bg color (approximation)
    d = ImageDraw.Draw(img)
    # Redraw outline as rounded
    # We'll just leave it as a rectangle — close enough at this scale
    text_anchor(d, 70, 48, "SRE COPILOT — Roadmap du Projet", F_TITLE, WHITE)
    text_anchor(d, 70, 90, "PFE IFS 013/26 — PwC DigiTech | Cloud Native Operations | Auteur: Ghada Ben Mansour",
                F_SUBTITLE, (220, 230, 235))
    text_anchor(d, 1330, 45, "100%", F_HUGE, WHITE, anchor="rt")
    text_anchor(d, 1330, 90, "avancement technique", F_SUBTITLE, (220, 230, 235), anchor="rt")
    text_anchor(d, 1330, 108, "5 / 5 missions", F_SUBTITLE, (220, 230, 235), anchor="rt")

    # ── "Tu es ici" pill ──────────────────────────────────────────────────────
    pill_x, pill_y = 645, 170
    rrect(d, pill_x, pill_y, 110, 22, 11, fill=ORANGE)
    text_anchor(d, pill_x + 55, pill_y + 11, "▼ TU ES ICI", F_PILL, WHITE, anchor="mm")

    # ── Progress timeline ─────────────────────────────────────────────────────
    line_y = 230
    # Background line
    d.line([(170, line_y), (1230, line_y)], fill=BORDER, width=6)
    # Done portion (M1 → M5 ALL done!)
    d.line([(170, line_y), (1230, line_y)], fill=GREEN_DARK, width=6)

    # 5 nodes — toutes complétées
    nodes = [
        (170,  "1", "MISSION 1", True),
        (435,  "2", "MISSION 2", True),
        (700,  "3", "MISSION 3", True),
        (965,  "4", "MISSION 4", True),
        (1230, "5", "MISSION 5", True),
    ]
    for cx, num, label, done in nodes:
        if done:
            d.ellipse((cx - 22, line_y - 22, cx + 22, line_y + 22), fill=GREEN_DARK)
            text_anchor(d, cx, line_y, "✓", F_NODE_NUM, WHITE, anchor="mm")
        else:
            ring_color = ORANGE if num == "4" else MUTED
            d.ellipse((cx - 22, line_y - 22, cx + 22, line_y + 22),
                      fill=WHITE, outline=ring_color, width=3)
            text_anchor(d, cx, line_y, num, F_NODE_NUM_SM, ring_color, anchor="mm")
        text_anchor(d, cx, line_y + 35, label, F_NODE, NAVY if done else MUTED, anchor="mt")

    # ── Cards ─────────────────────────────────────────────────────────────────
    cards_y = 290
    card_x_positions = [40, 308, 576, 844, 1112]

    cards = [
        {
            "status": "done", "num": "1",
            "title1": "Infrastructure", "title2": "KinD",
            "description": ["Cluster Kubernetes local", "+ stack monitoring"],
            "items": ["KinD (3 nœuds)", "Prometheus", "Grafana", "Alertmanager", "ArgoCD", "n8n (Docker)", "5 namespaces"],
            "tools": ["Docker Desktop, Helm,", "kubectl, KinD CLI"],
            "pct": 100, "time_est": "Terminée",
        },
        {
            "status": "done", "num": "2",
            "title1": "Pipeline", "title2": "d'alertes",
            "description": ["Alertmanager → n8n →", "SRE Agent"],
            "items": ["PrometheusRule", "AM routes (ns=demo)", "Workflow n8n 5 nœuds", "Filter + Dedup TTL", "responseMode:onReceived", "maxConcurrent=1"],
            "tools": ["Alertmanager v0.27,", "n8n 1.82, webhook"],
            "pct": 100, "time_est": "Terminée",
        },
        {
            "status": "done", "num": "3 · DERNIÈRE",
            "title1": "Agent IA +", "title2": "Auto-remédiation",
            "description": ["Pipeline 3 phases", "+ Dashboard centralisée"],
            "items": ["Phase 1: kubectl", "Phase 2: Mistral JSON", "Phase 3: scale + git", "Token ArgoCD permanent", "Dashboard /dashboard", "API /stats /incidents"],
            "tools": ["FastAPI, LangChain,", "Ollama, Chart.js"],
            "pct": 100, "time_est": "Terminée",
            "highlight": True,
        },
        {
            "status": "done", "num": "4",
            "title1": "Politiques", "title2": "Kyverno",
            "description": ["Sécurité & conformité", "des workloads K8s"],
            "items": ["Kyverno installé (Helm)", "no-privileged", "image-tag ≠ latest", "require-labels", "require-resource-limits", "Mode Audit", "PolicyReports actifs"],
            "tools": ["Kyverno, kubectl,", "ClusterPolicies"],
            "pct": 100, "time_est": "Terminée",
        },
        {
            "status": "done", "num": "5 · FINALE",
            "title1": "Métriques +", "title2": "Grafana",
            "description": ["Observabilité MTTR", "+ Dashboard SRE"],
            "items": ["Endpoint /metrics", "sre_alerts_total", "sre_remediated_total", "histogram duration", "ServiceMonitor scrape", "Dashboard Grafana auto", "9 panels KPI"],
            "tools": ["prometheus_client,", "Grafana, PromQL"],
            "pct": 100, "time_est": "Terminée",
        },
    ]

    for x, c in zip(card_x_positions, cards):
        draw_card(img, x, cards_y, **{k: v for k, v in c.items() if k != "highlight"},
                  highlight=c.get("highlight", False))

    # ── Footer / Legend ───────────────────────────────────────────────────────
    foot_y = 850
    rrect(d, 40, foot_y, 1320, 90, 10, fill=WHITE, outline=BORDER)

    text_anchor(d, 60, foot_y + 18, "LÉGENDE", F_LABEL, NAVY)

    # Done legend
    d.ellipse((52, foot_y + 42, 70, foot_y + 60), fill=GREEN_DARK)
    text_anchor(d, 61, foot_y + 51, "✓", F_NODE, WHITE, anchor="mm")
    text_anchor(d, 78, foot_y + 51, "Mission terminée et validée", F_LEG, TEXT, anchor="lm")

    # Todo legend
    d.ellipse((272, foot_y + 42, 290, foot_y + 60), fill=WHITE, outline=ORANGE, width=2)
    text_anchor(d, 281, foot_y + 51, "○", F_NODE, ORANGE, anchor="mm")
    text_anchor(d, 298, foot_y + 51, "Mission à réaliser", F_LEG, TEXT, anchor="lm")

    text_anchor(d, 60, foot_y + 75, "Document généré le 03/06/2026 — figure rapport/figures/roadmap.png",
                F_SUBTITLE, MUTED)

    # Done indicator (right) — projet complet
    GREEN_BG_RGB = (226, 239, 218)
    rrect(d, 840, foot_y + 18, 500, 55, 6, fill=GREEN_BG_RGB)
    text_anchor(d, 860, foot_y + 32, "PROJET TECHNIQUE COMPLET", F_NEXT_LBL, GREEN_DARK)
    text_anchor(d, 860, foot_y + 55, "Les 5 missions sont livrées. Prochaine étape : rédaction du rapport.",
                F_NEXT_TXT, NAVY)

    # ── Save ──────────────────────────────────────────────────────────────────
    out_path = os.path.join(os.path.dirname(__file__), "..", "rapport", "figures", "roadmap.png")
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    print(f"[OK] PNG saved: {out_path}")


if __name__ == "__main__":
    main()
