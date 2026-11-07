"""Generate the FinSight system architecture diagram (docs/architecture.png).

Usage:  python make_architecture.py
Output: architecture.png (embedded in the M1 proposal and final report).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ---- palette -------------------------------------------------------------
NAVY = "#0F2A43"; BLUE = "#1F6FB2"; LIGHT = "#E8F1F8"; ACCENT = "#0FA3A3"
GREY = "#5A6B7B"; ORANGE = "#E8871E"; BG = "#FFFFFF"

fig, ax = plt.subplots(figsize=(13.2, 8.4), dpi=150)
ax.set_xlim(0, 132); ax.set_ylim(0, 84); ax.axis("off")
fig.patch.set_facecolor(BG)


def box(x, y, w, h, fc, ec, lw=1.4, r=2.0, ls="-"):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.6,rounding_size={r}",
                       facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls, zorder=2)
    ax.add_patch(p)
    return p


def text(x, y, s, size=10.5, color=NAVY, weight="normal", ha="center"):
    ax.text(x, y, s, fontsize=size, color=color, fontweight=weight,
            ha=ha, va="center", zorder=3)


def arrow(x1, y1, x2, y2, color=GREY, style="-|>", lw=1.6, ls="-"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
                        color=color, linewidth=lw, linestyle=ls, zorder=1)
    ax.add_patch(a)


# ---- title ---------------------------------------------------------------
text(66, 80.5, "FinSight — System Architecture", size=17, weight="bold")
text(66, 76.6, "AI Robo-Advisor & Portfolio Optimization Dashboard  |  COM3115 FinTech Project (Track 2)",
     size=10, color=GREY)

# ---- layer bands ---------------------------------------------------------
box(2, 56, 128, 16, LIGHT, BLUE, lw=1.0, ls=(0, (4, 3)))
text(9, 70.2, "CLIENT\nLAYER", size=8, color=BLUE, weight="bold")
box(2, 33, 128, 17, LIGHT, ACCENT, lw=1.0, ls=(0, (4, 3)))
text(9, 48.2, "API\nLAYER", size=8, color=ACCENT, weight="bold")
box(2, 10, 128, 19, LIGHT, ORANGE, lw=1.0, ls=(0, (4, 3)))
text(9, 27.2, "SERVICE\nLAYER", size=8, color=ORANGE, weight="bold")
box(2, 1.5, 128, 6, "#F4F4F4", GREY, lw=1.0)
text(9, 5.8, "DATA LAYER", size=8, color=GREY, weight="bold")

# ---- client layer --------------------------------------------------------
box(20, 58, 44, 12, BG, BLUE, lw=1.6)
text(42, 67.0, "React SPA  (Vite + Recharts)", size=11.5, weight="bold")
text(42, 62.6, "Risk Questionnaire · Dashboard · Compliance Center", size=9, color=GREY)

box(72, 58, 40, 12, BG, BLUE, lw=1.2)
text(92, 67.0, "Dashboard Views", size=10.5, weight="bold")
text(92, 64.0, "Efficient Frontier · Allocation Pie", size=8.6, color=GREY)
text(92, 61.4, "Backtest Equity Curve · EDA Explorer", size=8.6, color=GREY)

box(118, 58, 10, 12, BG, BLUE, lw=1.2)
text(123, 64.5, "User", size=10, weight="bold")

arrow(118, 64, 112.5, 64, color=BLUE)
arrow(72, 64, 64.5, 64, color=BLUE)

# ---- API layer -----------------------------------------------------------
box(20, 35, 92, 13, BG, ACCENT, lw=1.6)
text(66, 45.4, "FastAPI Application  (Python 3.13)", size=11.5, weight="bold")
text(66, 41.6, "REST / JSON  ·  Pydantic validation  ·  CORS", size=9, color=GREY)
for i, ep in enumerate(["POST /api/profile", "POST /api/optimize", "GET /api/frontier",
                        "POST /api/backtest", "GET /api/market/{ticker}"]):
    x = 24.5 + i * 17.6
    box(x, 36.2, 16.2, 3.4, "#DDF0EE", ACCENT, lw=0.9, r=1.2)
    text(x + 8.1, 37.9, ep, size=7.6, color=NAVY)

arrow(42, 58, 42, 48.5, color=ACCENT)
text(45.5, 53.2, "HTTPS (dev: localhost:5173 → 8000)", size=8, color=GREY, ha="left")

# ---- service layer -------------------------------------------------------
svc = [
    ("DataService", "yfinance downloader\nSQLite price cache", 24),
    ("OptimizerService", "PyPortfolioOpt\nMarkowitz / Max-Sharpe", 52),
    ("MLService", "scikit-learn RF\nwalk-forward CV", 80),
    ("BacktestService", "vectorized backtest\nCAGR·Sharpe·MDD", 106),
]
for name, desc, x in svc:
    box(x, 12.5, 22, 14, BG, ORANGE, lw=1.6)
    text(x + 11, 23.6, name, size=10.5, weight="bold", color=NAVY)
    for j, line in enumerate(desc.split("\n")):
        text(x + 11, 19.8 - j * 3.0, line, size=8.2, color=GREY)

arrow(40, 35, 36, 26.5, color=ORANGE)
arrow(60, 35, 64, 26.5, color=ORANGE)
arrow(80, 35, 90, 26.5, color=ORANGE)
arrow(96, 35, 116, 26.5, color=ORANGE)

# ---- data layer ----------------------------------------------------------
box(24, 2.6, 30, 4.6, BG, GREY, lw=1.3, r=1.4)
text(39, 4.9, "Yahoo Finance API", size=9, weight="bold")
box(62, 2.6, 30, 4.6, BG, GREY, lw=1.3, r=1.4)
text(77, 4.9, "SQLite price cache", size=9, weight="bold")
box(100, 2.6, 30, 4.6, BG, GREY, lw=1.3, r=1.4)
text(115, 4.9, "fitted sklearn models", size=9, weight="bold")

arrow(35, 12.5, 37, 7.2, color=GREY, ls=(0, (3, 2)))
arrow(76, 12.5, 77, 7.2, color=GREY, ls=(0, (3, 2)))
arrow(116, 12.5, 115, 7.2, color=GREY, ls=(0, (3, 2)))
arrow(46, 4.9, 62, 4.9, color=GREY, ls=(0, (3, 2)), style="<|-|>")

# ---- footnote ------------------------------------------------------------
text(66, -0.8, "Solid arrows: runtime call flow · Dashed arrows: data access · Educational prototype, not SFC-licensed advice",
     size=7.5, color=GREY)

plt.savefig("architecture.png", bbox_inches="tight", facecolor=BG)
print("saved architecture.png")
