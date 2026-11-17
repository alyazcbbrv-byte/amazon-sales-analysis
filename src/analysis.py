"""
Analiz: data/processed/ CSV fayllarından əsas göstəriciləri hesablayır,
qrafikləri reports/figures/ qovluğuna, xülasəni reports/summary.md faylına yazır.

İstifadə:
    python src/analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
FIG = ROOT / "reports" / "figures"
REPORT = ROOT / "reports" / "summary.md"

AYLAR = ["Yan", "Fev", "Mar", "Apr", "May", "İyn", "İyl", "Avq", "Sen", "Okt", "Noy", "Dek"]
AYLAR_TAM = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "İyun", "İyul", "Avqust", "Sentyabr",
             "Oktyabr", "Noyabr", "Dekabr"]


# ----------------------------------------------------------------------------- data
def load() -> dict[str, pd.DataFrame]:
    sales = pd.read_csv(DATA / "sales.csv", parse_dates=["Tarix"], dtype={"Mehsul_kodu": str})
    city = pd.read_csv(DATA / "city.csv")
    sku = pd.read_csv(DATA / "sku.csv", dtype=str)
    stock = pd.read_csv(DATA / "stock.csv", parse_dates=["Tarix"], dtype={"Mehsul_kodu": str})
    sales = sales.merge(sku[["Mehsul_kodu", "Kateqoriya", "Olcu"]], on="Mehsul_kodu", how="left")
    sales = sales.merge(city[["Seher_ID", "Seher_Stat", "Stat"]], on="Seher_ID", how="left")
    sales["Il"] = sales["Tarix"].dt.year
    sales["Ay"] = sales["Tarix"].dt.month
    return {"sales": sales, "city": city, "sku": sku, "stock": stock}


def yearly_kpis(s: pd.DataFrame) -> pd.DataFrame:
    # Qeyd: Sifaris_ID mənbədə unikal deyil (eyni ID-lər hər il təkrarlanır),
    # ona görə hər sətir ayrıca satış əməliyyatı kimi sayılır.
    k = s.groupby("Il").agg(Satis=("Satis", "sum"), Emeliyyat=("Satis", "size"),
                            Mehsul=("Mehsul_kodu", "nunique"))
    k["Orta_emeliyyat"] = k["Satis"] / k["Emeliyyat"]
    k["Illik_artim"] = k["Satis"].pct_change()
    return k


def save(fig, name: str) -> str:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return f"figures/{name}"


# ----------------------------------------------------------------------------- charts
def draw_yearly(ax, k: pd.DataFrame, compact: bool = False) -> None:
    years = k.index.astype(str)
    colors = [S.MUTED] * (len(k) - 1) + [S.ORANGE]
    bars = ax.bar(years, k["Satis"], color=colors, width=0.62)
    for b, g in zip(bars, k["Illik_artim"]):
        h = b.get_height()
        x = b.get_x() + b.get_width() / 2
        ax.text(x, h, S.fmt_money(h), ha="center", va="bottom", fontsize=9 if compact else 10,
                fontweight="bold", color=S.TEXT, transform=ax.transData)
        if not pd.isna(g):
            ax.text(x, h * 0.5, f"{g:+.1%}", ha="center", va="center", fontsize=9,
                    color="white", fontweight="bold")
    ax.yaxis.set_major_formatter(S.millions)
    ax.set_ylim(0, k["Satis"].max() * 1.15)
    if compact:
        ax.set_yticks([])
        ax.grid(False)


def chart_yearly(k: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 4.4))
    draw_yearly(ax, k)
    S.titles(ax, "Satış 4 ildə 1.8 dəfə artıb",
             "İllik ümumi satış · sütunun içində illik artım faizi")
    S.source(fig)
    return save(fig, "01_illik_satis.png")


def draw_monthly(ax, m: pd.DataFrame, show_labels: bool = True) -> None:
    style = {2019: (S.MUTED, 1.4), 2020: (S.MUTED, 1.4), 2021: (S.SLATE, 2.0), 2022: (S.ORANGE, 2.8)}
    for col in m.columns:
        c, lw = style.get(col, (S.MUTED, 1.4))
        ax.plot(m.index, m[col], color=c, lw=lw, marker="o" if col == m.columns[-1] else None, ms=4,
                zorder=3 if col == m.columns[-1] else 2)
        if show_labels:
            ax.text(12.25, m[col].iloc[-1], str(col), color=c, va="center", fontsize=10,
                    fontweight="bold" if col >= 2021 else "normal")
    ax.set_xticks(range(1, 13), AYLAR)
    ax.set_xlim(0.7, 12.9 if show_labels else 12.3)
    ax.yaxis.set_major_formatter(S.millions)


def chart_monthly(s: pd.DataFrame) -> str:
    m = s.pivot_table(index="Ay", columns="Il", values="Satis", aggfunc="sum")
    fig, ax = plt.subplots(figsize=(10, 4.6))
    draw_monthly(ax, m)
    S.titles(ax, "2022 hər ay əvvəlki illərdən yüksəkdir",
             "Aylar üzrə satış · 2022 vurğulanıb, 2019–2020 boz")
    S.source(fig)
    return save(fig, "02_ayliq_trend.png")


def category_table(s: pd.DataFrame, top: int = 8) -> pd.Series:
    c = s.groupby("Kateqoriya")["Satis"].sum().sort_values(ascending=False)
    head = c.head(top)
    rest = c.iloc[top:].sum()
    if rest > 0:
        head = pd.concat([head, pd.Series({f"Digər ({len(c) - top})": rest})])
    return head


def draw_category(ax, cat: pd.Series, compact: bool = False) -> None:
    total = cat.sum()
    data = cat.iloc[::-1]
    colors = [S.MUTED if n.startswith("Digər") else (S.NAVY if i >= len(data) - 3 else S.SLATE)
              for i, n in enumerate(data.index)]
    ax.barh(data.index, data.values, color=colors, height=0.68)
    for y, v in enumerate(data.values):
        ax.text(v + total * 0.005, y, f"  {v/total:.1%}" if compact else f"  {S.fmt_money(v)} · {v/total:.1%}",
                va="center", fontsize=9, color=S.TEXT)
    ax.set_xlim(0, data.max() * (1.25 if compact else 1.35))
    ax.grid(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=9, colors=S.TEXT)


def chart_category(s: pd.DataFrame) -> tuple[str, pd.Series]:
    cat = category_table(s)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    draw_category(ax, cat)
    top3 = cat.head(3).sum() / cat.sum()
    S.titles(ax, f"3 kateqoriya satışın {top3:.0%}-ni verir",
             "Kateqoriyalar üzrə ümumi satış, 2019–2022")
    S.source(fig)
    share = s.groupby("Kateqoriya")["Satis"].sum()
    return save(fig, "03_kateqoriya.png"), (share / share.sum()).sort_values(ascending=False)


def chart_states(s: pd.DataFrame) -> tuple[str, pd.Series]:
    all_st = s.groupby("Stat")["Satis"].sum()
    st = all_st.nlargest(10)
    data = st.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    colors = [S.ORANGE if i == len(data) - 1 else S.NAVY for i in range(len(data))]
    ax.barh(data.index, data.values, color=colors, height=0.68)
    for y, v in enumerate(data.values):
        ax.text(v, y, f"  {S.fmt_money(v)}", va="center", fontsize=9, color=S.TEXT)
    ax.set_xlim(0, data.max() * 1.18)
    ax.grid(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", colors=S.TEXT)
    S.titles(ax, f"Top 10 ştat satışın {st.sum()/all_st.sum():.0%}-ni təşkil edir",
             "Ştatlar üzrə ümumi satış, 2019–2022")
    S.source(fig)
    return save(fig, "04_top_statlar.png"), st


def chart_type(s: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    t = s.pivot_table(index="Il", columns="Tip", values="Satis", aggfunc="sum")
    pct = t.div(t.sum(axis=1), axis=0).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    left = pd.Series(0.0, index=pct.index)
    colors = {"A": S.NAVY, "B": S.TEAL, "C": S.ORANGE}
    for col in pct.columns:
        ax.barh(pct.index.astype(str), pct[col], left=left, color=colors.get(col, S.SLATE),
                height=0.62, label=f"Tip {col}", edgecolor="white", linewidth=1.5)
        for y, (l, v) in enumerate(zip(left, pct[col])):
            if v > 0.06:
                ax.text(l + v / 2, y, f"{v:.0%}", ha="center", va="center", color="white",
                        fontsize=10, fontweight="bold")
        left += pct[col]
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.grid(False)
    ax.set_xticks([])
    ax.legend(ncol=3, loc="lower right", bbox_to_anchor=(1, 1.02), handlelength=1, handleheight=1)
    first, last = pct.iloc[-1], pct.iloc[0]   # pct tərsinə düzülüb
    S.titles(ax, f"A tipinin payı {first['A']:.0%}-dən {last['A']:.0%}-ə düşüb",
             "Hər il üzrə satışın A / B / C tipləri arasında bölgüsü")
    S.source(fig)
    return save(fig, "05_tip_payi.png"), pct.iloc[::-1]


def chart_heatmap(s: pd.DataFrame) -> str:
    m = s.pivot_table(index="Il", columns="Ay", values="Satis", aggfunc="sum")
    cmap = LinearSegmentedColormap.from_list("amz", ["#F4F6F9", "#9DB4CF", S.NAVY])
    fig, ax = plt.subplots(figsize=(10, 3.4))
    im = ax.imshow(m.values, cmap=cmap, aspect="auto")
    ax.set_xticks(range(12), AYLAR)
    ax.set_yticks(range(len(m.index)), m.index.astype(str))
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    vmin, vmax = m.values.min(), m.values.max()
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            dark = (v - vmin) / (vmax - vmin) > 0.55
            ax.text(j, i, f"{v/1e6:.0f}", ha="center", va="center", fontsize=9,
                    color="white" if dark else S.TEXT, fontweight="bold" if dark else "normal")
    ax.set_xticks([x - 0.5 for x in range(1, 12)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, m.shape[0])], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    S.titles(ax, "Mövsümilik xəritəsi", "Ay × il üzrə satış, milyon")
    S.source(fig)
    return save(fig, "07_movsumilik.png")


def chart_stock(s: pd.DataFrame, stock: pd.DataFrame, sku: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """Stok gündəlik snapshot-dır: tarixlər üzrə cəmlənmir, orta götürülür."""
    st = stock.merge(sku[["Mehsul_kodu", "Kateqoriya"]], on="Mehsul_kodu", how="left")
    daily = st.groupby("Tarix")["Stock"].sum()
    monthly_stock = daily.resample("MS").mean()
    monthly_sold = s.set_index("Tarix").resample("MS")["Satis"].size()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1], "hspace": 0.35})
    ax1.fill_between(monthly_sold.index, monthly_sold.values, color=S.NAVY, alpha=0.12, step="mid")
    ax1.plot(monthly_sold.index, monthly_sold.values, color=S.NAVY, lw=2, drawstyle="steps-mid")
    ax1.yaxis.set_major_formatter(S.thousands)
    ax1.text(0, 1.04, "Satış əməliyyatı (ay üzrə)", transform=ax1.transAxes, fontsize=10, color=S.SUBTLE)

    ax2.plot(monthly_stock.index, monthly_stock.values, color=S.ORANGE, lw=2)
    ax2.axhline(monthly_stock.mean(), color=S.MUTED, lw=1, ls="--")
    ax2.text(monthly_stock.index[0], monthly_stock.mean(), " orta", color=S.SUBTLE, fontsize=8, va="bottom")
    ax2.yaxis.set_major_formatter(S.thousands)
    ax2.text(0, 1.04, "Orta gündəlik stok qalığı (ədəd)", transform=ax2.transAxes, fontsize=10, color=S.SUBTLE)

    growth = monthly_sold.iloc[-12:].mean() / monthly_sold.iloc[:12].mean() - 1
    fig.text(0.125, 0.985, f"Satış həcmi {growth:+.0%} artıb, stok isə eyni səviyyədə qalıb",
             fontsize=14, fontweight="bold", color=S.TEXT, va="top")
    S.source(fig)
    by_cat = (st.groupby(["Kateqoriya", "Tarix"])["Stock"].sum().groupby("Kateqoriya").mean()
              .rename("Orta_gundelik_stok").to_frame())
    by_cat["Mehsul_sayi"] = st.groupby("Kateqoriya")["Mehsul_kodu"].nunique()
    return save(fig, "06_stok_trend.png"), by_cat.sort_values("Orta_gundelik_stok", ascending=False)


def kpi_tile(fig, rect, label: str, value: str, note: str, note_color: str) -> None:
    ax = fig.add_axes(rect)
    ax.set_axis_off()
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.06",
                                transform=ax.transAxes, facecolor="#F6F8FB", edgecolor=S.LIGHT))
    ax.text(0.07, 0.75, label.upper(), fontsize=8.5, color=S.SUBTLE, fontweight="bold", transform=ax.transAxes)
    ax.text(0.07, 0.38, value, fontsize=20, color=S.NAVY, fontweight="bold", transform=ax.transAxes)
    ax.text(0.07, 0.13, note, fontsize=9, color=note_color, transform=ax.transAxes)


def chart_overview(s: pd.DataFrame, k: pd.DataFrame) -> str:
    """README üçün bir səhifəlik icmal (dashboard görünüşü)."""
    fig = plt.figure(figsize=(14, 8))
    fig.text(0.03, 0.965, "Amazon satış icmalı · 2019–2022", fontsize=20, fontweight="bold", color=S.TEXT)
    fig.text(0.03, 0.93, "Geyim kateqoriyaları üzrə ABŞ satışları", fontsize=11, color=S.SUBTLE)

    total = s["Satis"].sum()
    cagr = (k["Satis"].iloc[-1] / k["Satis"].iloc[0]) ** (1 / (len(k) - 1)) - 1
    last, prev = k.iloc[-1], k.iloc[-2]
    tiles = [
        ("Ümumi satış", S.fmt_money(total), "4 il üzrə", S.SUBTLE),
        (f"{k.index[-1]} satışı", S.fmt_money(last["Satis"]), f"▲ {last['Illik_artim']:.1%} əvvəlki ilə görə", S.GOOD),
        ("Orta illik artım", f"{cagr:.1%}", "CAGR 2019→2022", S.SUBTLE),
        ("Orta əməliyyat dəyəri", f"{total/len(s):,.0f}",
         f"4 ildə sabit · artım həcm hesabına", S.SUBTLE),
    ]
    w, gap, x0 = 0.225, 0.015, 0.03
    for i, t in enumerate(tiles):
        kpi_tile(fig, [x0 + i * (w + gap), 0.73, w, 0.15], *t)

    ax1 = fig.add_axes([0.03, 0.07, 0.25, 0.53])
    draw_yearly(ax1, k, compact=True)
    ax1.spines["bottom"].set_color(S.MUTED)
    ax1.text(0, 1.06, "İllik satış", transform=ax1.transAxes, fontsize=12, fontweight="bold")

    ax2 = fig.add_axes([0.34, 0.07, 0.34, 0.53])
    m = s.pivot_table(index="Ay", columns="Il", values="Satis", aggfunc="sum")
    draw_monthly(ax2, m)
    ax2.text(0, 1.06, "Aylar üzrə satış", transform=ax2.transAxes, fontsize=12, fontweight="bold")

    ax3 = fig.add_axes([0.81, 0.07, 0.17, 0.53])
    draw_category(ax3, category_table(s, top=7), compact=True)
    ax3.text(-0.62, 1.06, "Kateqoriya payı", transform=ax3.transAxes, fontsize=12, fontweight="bold")

    S.source(fig)
    return save(fig, "00_icmal.png")


# ----------------------------------------------------------------------------- report
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    S.apply()
    d = load()
    s = d["sales"]

    k = yearly_kpis(s)
    figs = {"overview": chart_overview(s, k), "yearly": chart_yearly(k), "monthly": chart_monthly(s)}
    figs["category"], cat_share = chart_category(s)
    figs["states"], top_states = chart_states(s)
    figs["type"], type_pct = chart_type(s)
    figs["stock"], stock_df = chart_stock(s, d["stock"], d["sku"])
    figs["heatmap"] = chart_heatmap(s)

    best_month = s.groupby(["Il", "Ay"])["Satis"].sum()
    bm_year, bm_month = best_month.idxmax()
    monthly_avg = s.groupby("Ay")["Satis"].sum()

    total = s["Satis"].sum()
    cagr = (k["Satis"].iloc[-1] / k["Satis"].iloc[0]) ** (1 / (len(k) - 1)) - 1

    lines = [
        "# Amazon satış analizi — xülasə",
        "",
        "_Bu fayl `python src/analysis.py` ilə avtomatik yaradılır._",
        "",
        f"![İcmal]({figs['overview']})",
        "",
        "## Əsas göstəricilər",
        "",
        f"- Ümumi satış (2019–2022): **{total:,.0f}**",
        f"- Satış əməliyyatı: **{len(s):,}**, orta əməliyyat dəyəri: **{total/len(s):,.0f}**",
        f"- Orta illik artım (CAGR): **{cagr:.1%}**",
        f"- Ən güclü ay: **{AYLAR_TAM[bm_month-1]} {bm_year}** ({best_month.max():,.0f})",
        f"- 4 ilin cəmində ən yüksək satış **{AYLAR_TAM[monthly_avg.idxmax()-1]}**, "
        f"ən aşağı **{AYLAR_TAM[monthly_avg.idxmin()-1]}** ayındadır",
        "",
        "## İllər üzrə",
        "",
        "| İl | Satış | İllik artım | Əməliyyat | Orta əməliyyat dəyəri | Məhsul (SKU) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for il, r in k.iterrows():
        g = "—" if pd.isna(r["Illik_artim"]) else f"{r['Illik_artim']:+.1%}"
        lines.append(f"| {il} | {r['Satis']:,.0f} | {g} | {r['Emeliyyat']:,.0f} | {r['Orta_emeliyyat']:,.0f} | {r['Mehsul']:,.0f} |")
    lines += ["", f"![İllik satış]({figs['yearly']})", "", f"![Aylıq trend]({figs['monthly']})", "",
              f"![Mövsümilik]({figs['heatmap']})", "",
              "## Kateqoriyalar", "", "| Kateqoriya | Satışdakı payı |", "|---|---:|"]
    lines += [f"| {c} | {v:.1%} |" for c, v in cat_share.items()]
    lines += ["", f"![Kateqoriyalar]({figs['category']})", "",
              "## Coğrafiya — top 10 ştat", "", "| Ştat | Satış |", "|---|---:|"]
    lines += [f"| {c} | {v:,.0f} |" for c, v in top_states.items()]
    lines += ["", f"![Top ştatlar]({figs['states']})", "",
              "## Satış tipi (A / B / C)", "", "| İl | " + " | ".join(f"Tip {c}" for c in type_pct.columns) + " |",
              "|---|" + "---:|" * len(type_pct.columns)]
    lines += [f"| {il} | " + " | ".join(f"{v:.1%}" for v in r) + " |" for il, r in type_pct.iterrows()]
    lines += ["", f"![Tip payı]({figs['type']})", "",
              "## Stok", "",
              "Stok cədvəli gündəlik snapshot-dır, ona görə dəyərlər tarixlər üzrə cəmlənmir — günlük cəmin ortası götürülür.", "",
              "| Kateqoriya | Orta gündəlik stok | Stokda izlənən SKU |", "|---|---:|---:|"]
    lines += [f"| {c} | {r['Orta_gundelik_stok']:,.0f} | {r['Mehsul_sayi']:,.0f} |"
              for c, r in stock_df.head(10).iterrows()]
    lines += ["", f"![Stok]({figs['stock']})", ""]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
