"""Bütün qrafiklər üçün vahid vizual üslub (Power BI teması ilə eyni palitra)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# Palitra — powerbi/theme/amazon_theme.json ilə eynidir
NAVY = "#14213D"      # əsas rəng / vurğu
ORANGE = "#F28C28"    # ikinci vurğu (cari il, ən yaxşı dəyər)
TEAL = "#2A9D8F"
SLATE = "#5C677D"
MUTED = "#B8C0CC"     # fon elementləri, köhnə illər
LIGHT = "#E9EDF2"
TEXT = "#1F2933"
SUBTLE = "#6B7785"
GOOD = "#2A9D8F"
BAD = "#D1495B"

SERIES = [NAVY, ORANGE, TEAL, SLATE, "#8E7DBE", "#E9C46A"]


def apply() -> None:
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
        "font.size": 10,
        "text.color": TEXT,
        "axes.labelcolor": SUBTLE,
        "axes.edgecolor": MUTED,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": LIGHT,
        "grid.linewidth": 1,
        "axes.axisbelow": True,
        "xtick.color": SUBTLE,
        "ytick.color": SUBTLE,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "figure.dpi": 110,
        "savefig.dpi": 160,
    })


def titles(ax, title: str, subtitle: str | None = None) -> None:
    """Sola düzlənmiş başlıq + boz alt başlıq (hesabat üslubu)."""
    ax.set_title("")
    y = 1.13 if subtitle else 1.05
    ax.text(0, y, title, transform=ax.transAxes, fontsize=14, fontweight="bold", color=TEXT, va="bottom")
    if subtitle:
        ax.text(0, 1.04, subtitle, transform=ax.transAxes, fontsize=10, color=SUBTLE, va="bottom")


def source(fig, text: str = "Mənbə: Amazon satış bazası, 2019–2022") -> None:
    fig.text(0.01, -0.04, text, fontsize=8, color=SUBTLE, ha="left", va="bottom")


def fmt_money(x: float) -> str:
    if abs(x) >= 1e9:
        return f"{x/1e9:.2f} mlrd"
    if abs(x) >= 1e6:
        return f"{x/1e6:.1f} mln"
    if abs(x) >= 1e3:
        return f"{x/1e3:.0f} min"
    return f"{x:,.0f}"


millions = mtick.FuncFormatter(lambda x, _: f"{x/1e6:,.0f} mln" if x else "0")
thousands = mtick.FuncFormatter(lambda x, _: f"{x/1e3:,.0f} min" if x else "0")
