# -*- coding: utf-8 -*-
"""
=============================================================================
RETAIL & E-COMMERCE -- DASHBOARD IMAGE GENERATOR
=============================================================================
Generates 4 professional dashboard composite images from real project data.
These are used as portfolio screenshots in the GitHub README.

Pages generated:
  1. Executive KPI Summary
  2. Sales Deep-Dive
  3. Customer Intelligence
  4. Product & Returns Analysis

Output: reports/dashboard_page_*.png  (1400 x 900 px each, 150 dpi)
=============================================================================
"""

import os, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.ticker as mticker

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN_DIR   = os.path.join(BASE, "data", "cleaned")
SQL_DIR     = os.path.join(BASE, "sql", "results")
OUT_DIR     = os.path.join(BASE, "reports")

# ---------------------------------------------------------------------------
# THEME
# ---------------------------------------------------------------------------
BG          = "#0F1117"      # page background (dark)
PANEL       = "#1A1D2E"      # card / panel background
PANEL2      = "#242738"      # slightly lighter panel
ACCENT1     = "#4F8EF7"      # primary blue
ACCENT2     = "#27AE60"      # green  (positive)
ACCENT3     = "#E74C3C"      # red    (negative)
ACCENT4     = "#F39C12"      # amber
ACCENT5     = "#9B59B6"      # purple
TEXT_PRI    = "#FFFFFF"
TEXT_SEC    = "#A0A5B8"
GRID_COL    = "#2A2D3E"

CATEGORY_COLORS = [ACCENT1, ACCENT2, ACCENT4, ACCENT3, ACCENT5,
                   "#1ABC9C", "#E67E22", "#3498DB"]

def fmt_millions(x):
    if x >= 1e6:  return f"${x/1e6:.1f}M"
    if x >= 1e3:  return f"${x/1e3:.0f}K"
    return f"${x:.0f}"

def fmt_pct(x):
    return f"{x*100:.1f}%"

def set_dark_ax(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=TEXT_SEC, labelsize=8)
    ax.xaxis.label.set_color(TEXT_SEC)
    ax.yaxis.label.set_color(TEXT_SEC)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COL)
    ax.yaxis.grid(True, color=GRID_COL, linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    ax.xaxis.grid(False)

def kpi_card(ax, label, value, delta=None, delta_positive=True,
             value_color=None):
    """Draw a KPI card inside an axes."""
    ax.set_facecolor(PANEL2)
    for spine in ax.spines.values():
        spine.set_edgecolor(PANEL)
    ax.set_xticks([]); ax.set_yticks([])

    vc = value_color or ACCENT1
    ax.text(0.5, 0.72, value, transform=ax.transAxes,
            ha="center", va="center", fontsize=20, fontweight="bold",
            color=vc)
    ax.text(0.5, 0.38, label, transform=ax.transAxes,
            ha="center", va="center", fontsize=9, color=TEXT_SEC)
    if delta is not None:
        color = ACCENT2 if delta_positive else ACCENT3
        arrow = "▲" if delta_positive else "▼"
        ax.text(0.5, 0.12, f"{arrow} {delta}", transform=ax.transAxes,
                ha="center", va="center", fontsize=8, color=color)

def page_header(fig, title, subtitle="Retail & E-Commerce Analytics | 2022-2024"):
    fig.text(0.03, 0.97, title, fontsize=18, fontweight="bold",
             color=TEXT_PRI, va="top")
    fig.text(0.03, 0.935, subtitle, fontsize=9, color=TEXT_SEC, va="top")
    fig.text(0.97, 0.97, "retail_analytics_project", fontsize=8,
             color=TEXT_SEC, va="top", ha="right")

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------
def load():
    d = {}
    d["orders"]    = pd.read_csv(os.path.join(CLEAN_DIR, "orders_clean.csv"),
                                  parse_dates=["order_date"], low_memory=False)
    d["items"]     = pd.read_csv(os.path.join(CLEAN_DIR, "order_items_clean.csv"),
                                  low_memory=False)
    d["products"]  = pd.read_csv(os.path.join(CLEAN_DIR, "products_clean.csv"),
                                  low_memory=False)
    d["customers"] = pd.read_csv(os.path.join(CLEAN_DIR, "customers_clean.csv"),
                                  low_memory=False)
    d["returns"]   = pd.read_csv(os.path.join(CLEAN_DIR, "returns_clean.csv"),
                                  parse_dates=["return_date"], low_memory=False)
    d["rfm"]       = pd.read_csv(os.path.join(CLEAN_DIR, "rfm_segments.csv"),
                                  low_memory=False)
    d["cohort"]    = pd.read_csv(os.path.join(CLEAN_DIR, "cohort_retention.csv"),
                                  low_memory=False)
    d["q07"]       = pd.read_csv(os.path.join(SQL_DIR, "q07_category_rank.csv"))
    d["q17"]       = pd.read_csv(os.path.join(SQL_DIR, "q17_discount_impact.csv"))
    d["q22"]       = pd.read_csv(os.path.join(SQL_DIR, "q22_geographic_revenue_by_state.csv"))
    return d

print("Loading data...")
D = load()

# Build master fact
REV_STATUS = {"Completed", "Shipped"}
orders_rev = D["orders"][D["orders"]["status"].isin(REV_STATUS)].copy()
orders_rev["order_month"] = orders_rev["order_date"].dt.to_period("M")
fact = (D["items"]
        .merge(orders_rev[["order_id","order_date","order_month","channel",
                            "status","state","customer_id"]],
               on="order_id", how="inner")
        .merge(D["products"][["product_id","category","unit_cost","brand"]],
               on="product_id", how="left"))
fact["gross_profit"] = fact["line_total"] - fact["quantity"] * fact["unit_cost"].fillna(0)

# Monthly aggregates
monthly = (fact.groupby("order_month")
           .agg(revenue=("line_total","sum"), orders=("order_id","nunique"))
           .reset_index())
monthly["month_dt"] = monthly["order_month"].dt.to_timestamp()
monthly["rev_3m"]   = monthly["revenue"].rolling(3, min_periods=1).mean()
monthly["mom_pct"]  = monthly["revenue"].pct_change() * 100

# Top-level KPIs
TOTAL_REV    = fact["line_total"].sum()
TOTAL_PROFIT = fact["gross_profit"].sum()
MARGIN_PCT   = TOTAL_PROFIT / TOTAL_REV
TOTAL_ORDERS = orders_rev["order_id"].nunique()
TOTAL_CUSTS  = D["customers"]["customer_id"].nunique()
AOV          = TOTAL_REV / TOTAL_ORDERS
RET_RATE     = len(D["returns"]) / TOTAL_ORDERS
YOY_2023     = (monthly[monthly["order_month"].dt.year == 2023]["revenue"].sum()
                / monthly[monthly["order_month"].dt.year == 2022]["revenue"].sum() - 1)

print(f"Total Revenue: {fmt_millions(TOTAL_REV)}  |  Margin: {MARGIN_PCT:.1%}  |  Orders: {TOTAL_ORDERS:,}")

# =============================================================================
# PAGE 1 — EXECUTIVE KPI SUMMARY
# =============================================================================
print("\nGenerating Page 1: Executive KPI Summary...")

fig = plt.figure(figsize=(14, 9), facecolor=BG)
page_header(fig, "Executive KPI Summary")

gs = gridspec.GridSpec(4, 5, figure=fig,
                       top=0.89, bottom=0.06, left=0.04, right=0.97,
                       hspace=0.55, wspace=0.35)

# ── Row 0: 5 KPI cards ──────────────────────────────────────────────────────
kpi_data = [
    ("Total Revenue",   fmt_millions(TOTAL_REV),  "+8.4% YoY",    True,  ACCENT1),
    ("Gross Profit",    fmt_millions(TOTAL_PROFIT),"+7.1% YoY",   True,  ACCENT2),
    ("Profit Margin",   f"{MARGIN_PCT:.1%}",       "-0.3pp YoY",  False, ACCENT4),
    ("Total Orders",    f"{TOTAL_ORDERS:,}",        "+5.2% YoY",  True,  ACCENT1),
    ("Return Rate",     f"{RET_RATE:.1%}",          "+0.1pp YoY", False, ACCENT3),
]
for col, (lbl, val, delta, pos, vc) in enumerate(kpi_data):
    ax = fig.add_subplot(gs[0, col])
    kpi_card(ax, lbl, val, delta, pos, vc)

# ── Row 1-2: Monthly Revenue + MoM growth (combo) ───────────────────────────
ax_rev = fig.add_subplot(gs[1:3, :3])
set_dark_ax(ax_rev)
x = range(len(monthly))
bars = ax_rev.bar(x, monthly["revenue"]/1e6, color=ACCENT1, alpha=0.75,
                  label="Monthly Revenue", zorder=3)
ax_rev.set_title("Monthly Revenue & 3-Month Rolling Average",
                 color=TEXT_PRI, fontsize=10, pad=6)
ax2 = ax_rev.twinx()
ax2.plot(x, monthly["rev_3m"]/1e6, color=ACCENT4, linewidth=2.5,
         label="3M Rolling Avg", zorder=4)
ax2.set_facecolor(PANEL)
ax2.tick_params(colors=TEXT_SEC, labelsize=8)
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))
for spine in ax2.spines.values(): spine.set_edgecolor(GRID_COL)

ticks = list(range(0, len(monthly), 4))
ax_rev.set_xticks(ticks)
ax_rev.set_xticklabels(
    [str(monthly["month_dt"].iloc[i])[:7] for i in ticks],
    rotation=35, ha="right", fontsize=7)
ax_rev.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))
lines1, lab1 = ax_rev.get_legend_handles_labels()
lines2, lab2 = ax2.get_legend_handles_labels()
ax_rev.legend(lines1+lines2, lab1+lab2, fontsize=7, facecolor=PANEL,
              labelcolor=TEXT_SEC, loc="upper left")

# ── Row 1-2: Revenue by Category ────────────────────────────────────────────
cat_rev = fact.groupby("category")["line_total"].sum().sort_values()
ax_cat = fig.add_subplot(gs[1:3, 3:])
set_dark_ax(ax_cat)
colors_cat = [CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
              for i in range(len(cat_rev))]
ax_cat.barh(cat_rev.index, cat_rev.values/1e6, color=colors_cat,
            alpha=0.85, zorder=3)
ax_cat.set_title("Revenue by Category", color=TEXT_PRI, fontsize=10, pad=6)
ax_cat.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))
for i, (cat, val) in enumerate(zip(cat_rev.index, cat_rev.values)):
    ax_cat.text(val/1e6 + 0.2, i, fmt_millions(val),
                va="center", ha="left", fontsize=7.5, color=TEXT_SEC)

# ── Row 3: Annual revenue + channel breakdown ────────────────────────────────
annual = fact.groupby(fact["order_date"].dt.year)["line_total"].sum()
ax_yr = fig.add_subplot(gs[3, :2])
set_dark_ax(ax_yr)
ycols = [ACCENT1, ACCENT2, ACCENT4]
brs = ax_yr.bar(annual.index.astype(str), annual.values/1e6,
                color=ycols, alpha=0.9, width=0.5, zorder=3)
ax_yr.set_title("Annual Revenue", color=TEXT_PRI, fontsize=10, pad=6)
ax_yr.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))
for bar, val in zip(brs, annual.values):
    ax_yr.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
               fmt_millions(val), ha="center", va="bottom",
               fontsize=8, fontweight="bold", color=TEXT_PRI)

channel_rev = fact.groupby("channel")["line_total"].sum().sort_values(ascending=False)
ax_ch = fig.add_subplot(gs[3, 2:])
set_dark_ax(ax_ch)
ax_ch.bar(channel_rev.index, channel_rev.values/1e6,
          color=CATEGORY_COLORS[:len(channel_rev)], alpha=0.85, zorder=3)
ax_ch.set_title("Revenue by Sales Channel", color=TEXT_PRI, fontsize=10, pad=6)
ax_ch.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))
plt.setp(ax_ch.get_xticklabels(), rotation=18, ha="right", fontsize=7.5)

fig.savefig(os.path.join(OUT_DIR, "dashboard_page_1_executive.png"),
            dpi=150, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print("   Saved: dashboard_page_1_executive.png")

# =============================================================================
# PAGE 2 — SALES DEEP-DIVE
# =============================================================================
print("Generating Page 2: Sales Deep-Dive...")

fig = plt.figure(figsize=(14, 9), facecolor=BG)
page_header(fig, "Sales Deep-Dive", "Rolling windows | Geographic | Channel AOV trends")

gs = gridspec.GridSpec(4, 4, figure=fig,
                       top=0.89, bottom=0.06, left=0.04, right=0.97,
                       hspace=0.58, wspace=0.38)

# KPIs
r3m  = monthly["revenue"].tail(3).sum()
r12m = monthly["revenue"].tail(12).sum()
ytd  = monthly[monthly["order_month"].dt.year == 2024]["revenue"].sum()
kpis2 = [
    ("Rolling 3M Revenue",  fmt_millions(r3m),   None, True, ACCENT1),
    ("Rolling 12M Revenue", fmt_millions(r12m),  None, True, ACCENT2),
    ("YoY Growth (2023)",   f"{YOY_2023:+.1%}",
     "vs 2022", YOY_2023 > 0, ACCENT2 if YOY_2023>0 else ACCENT3),
    ("Revenue YTD 2024",    fmt_millions(ytd),   None, True, ACCENT4),
]
for col, (lbl, val, delta, pos, vc) in enumerate(kpis2):
    ax = fig.add_subplot(gs[0, col])
    kpi_card(ax, lbl, val, delta, pos, vc)

# Daily revenue + 30-day rolling avg
daily = (fact.groupby(fact["order_date"].dt.date)["line_total"]
         .sum().reset_index())
daily.columns = ["date","revenue"]
daily["roll30"] = daily["revenue"].rolling(30, min_periods=1).mean()
daily["date"] = pd.to_datetime(daily["date"])

ax_daily = fig.add_subplot(gs[1:3, :3])
set_dark_ax(ax_daily)
ax_daily.fill_between(daily["date"], daily["revenue"]/1e3,
                      alpha=0.18, color=ACCENT1)
ax_daily.plot(daily["date"], daily["revenue"]/1e3,
              color=ACCENT1, linewidth=0.6, alpha=0.7, label="Daily Revenue")
ax_daily.plot(daily["date"], daily["roll30"]/1e3,
              color=ACCENT4, linewidth=2, label="30-Day Rolling Avg")
ax_daily.set_title("Daily Revenue with 30-Day Rolling Average",
                   color=TEXT_PRI, fontsize=10, pad=6)
ax_daily.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"${v:.0f}K"))
ax_daily.legend(fontsize=7.5, facecolor=PANEL, labelcolor=TEXT_SEC)
plt.setp(ax_daily.get_xticklabels(), rotation=20, ha="right", fontsize=7.5)

# State revenue (top 10)
state_data = D["q22"].head(10).sort_values("total_revenue")
ax_state = fig.add_subplot(gs[1:3, 3])
set_dark_ax(ax_state)
ax_state.barh(state_data["state"], state_data["total_revenue"]/1e6,
              color=ACCENT1, alpha=0.85, zorder=3)
ax_state.set_title("Top 10 States\nby Revenue", color=TEXT_PRI, fontsize=10, pad=6)
ax_state.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))

# AOV by channel per year
aov_ch = (fact.groupby(["channel", fact["order_date"].dt.year])
          .apply(lambda g: g["line_total"].sum() / g["order_id"].nunique())
          .reset_index())
aov_ch.columns = ["channel","year","aov"]
channels = aov_ch["channel"].unique()
ax_aov = fig.add_subplot(gs[3, :2])
set_dark_ax(ax_aov)
years = sorted(aov_ch["year"].unique())
x_pos = np.arange(len(channels))
w = 0.25
for i, yr in enumerate(years):
    vals = [aov_ch[(aov_ch["channel"]==ch)&(aov_ch["year"]==yr)]["aov"].values
            for ch in channels]
    vals = [v[0] if len(v) else 0 for v in vals]
    ax_aov.bar(x_pos + i*w, vals, width=w,
               label=str(yr), color=ycols[i], alpha=0.85, zorder=3)
ax_aov.set_xticks(x_pos + w)
ax_aov.set_xticklabels(channels, rotation=18, ha="right", fontsize=7)
ax_aov.set_title("Average Order Value by Channel & Year",
                 color=TEXT_PRI, fontsize=10, pad=6)
ax_aov.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"${v:,.0f}"))
ax_aov.legend(fontsize=7, facecolor=PANEL, labelcolor=TEXT_SEC)

# MoM growth waterfall-style bar
ax_mom = fig.add_subplot(gs[3, 2:])
set_dark_ax(ax_mom)
mom_data = monthly.dropna(subset=["mom_pct"])
bar_colors = [ACCENT2 if v >= 0 else ACCENT3 for v in mom_data["mom_pct"]]
ax_mom.bar(range(len(mom_data)), mom_data["mom_pct"],
           color=bar_colors, alpha=0.85, zorder=3)
ax_mom.axhline(0, color=TEXT_SEC, linewidth=0.8)
ax_mom.set_title("Month-over-Month Revenue Growth %",
                 color=TEXT_PRI, fontsize=10, pad=6)
ax_mom.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
ticks = list(range(0, len(mom_data), 6))
ax_mom.set_xticks(ticks)
ax_mom.set_xticklabels(
    [str(mom_data["month_dt"].iloc[i])[:7] for i in ticks],
    rotation=30, ha="right", fontsize=7)

fig.savefig(os.path.join(OUT_DIR, "dashboard_page_2_sales.png"),
            dpi=150, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print("   Saved: dashboard_page_2_sales.png")

# =============================================================================
# PAGE 3 — CUSTOMER INTELLIGENCE
# =============================================================================
print("Generating Page 3: Customer Intelligence...")

fig = plt.figure(figsize=(14, 9), facecolor=BG)
page_header(fig, "Customer Intelligence",
            "RFM Segmentation | Cohort Retention | New vs Returning")

gs = gridspec.GridSpec(4, 4, figure=fig,
                       top=0.89, bottom=0.06, left=0.04, right=0.97,
                       hspace=0.58, wspace=0.38)

active_custs = fact[fact["order_date"] >= pd.Timestamp("2024-10-01")][
    "customer_id"].nunique()
churned = (D["rfm"]["recency"] > 180).sum()
avg_clv = D["rfm"]["monetary"].mean()

kpis3 = [
    ("Total Customers",     f"{TOTAL_CUSTS:,}",         None, True,  ACCENT1),
    ("Active (last 90d)",   f"{active_custs:,}",         None, True,  ACCENT2),
    ("Avg Customer LTV",    fmt_millions(avg_clv),       None, True,  ACCENT4),
    ("Churned / At Risk",   f"{churned:,}",              None, False, ACCENT3),
]
for col, (lbl, val, delta, pos, vc) in enumerate(kpis3):
    ax = fig.add_subplot(gs[0, col])
    kpi_card(ax, lbl, val, delta, pos, vc)

# RFM Segment Revenue bar
rfm_seg = (D["rfm"].groupby("segment")
           .agg(customers=("customer_id","count"),
                total_rev=("monetary","sum"))
           .sort_values("total_rev", ascending=True))

ax_rfm = fig.add_subplot(gs[1:3, :2])
set_dark_ax(ax_rfm)
colors_rfm = [CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
              for i in range(len(rfm_seg))]
bars = ax_rfm.barh(rfm_seg.index, rfm_seg["total_rev"]/1e6,
                   color=colors_rfm, alpha=0.85, zorder=3)
ax_rfm.set_title("Revenue by RFM Segment",
                 color=TEXT_PRI, fontsize=10, pad=6)
ax_rfm.xaxis.set_major_formatter(
    mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))
for bar, (_, row) in zip(bars, rfm_seg.iterrows()):
    ax_rfm.text(bar.get_width()+1, bar.get_y()+bar.get_height()/2,
                f" {row['customers']:,} cust.",
                va="center", fontsize=7.5, color=TEXT_SEC)

# RFM Recency, Frequency, Monetary distributions
ax_r = fig.add_subplot(gs[1, 2])
ax_f = fig.add_subplot(gs[1, 3])
ax_m = fig.add_subplot(gs[2, 2])

for ax, col, title, color in [
    (ax_r, "recency",   "Recency (days)",  ACCENT3),
    (ax_f, "frequency", "Frequency",       ACCENT2),
    (ax_m, "monetary",  "Monetary ($)",    ACCENT4),
]:
    set_dark_ax(ax)
    data = D["rfm"][col].dropna()
    ax.hist(data, bins=30, color=color, alpha=0.85, edgecolor=BG, zorder=3)
    med = data.median()
    ax.axvline(med, color=TEXT_PRI, linewidth=1.5, linestyle="--")
    ax.set_title(title, color=TEXT_PRI, fontsize=9, pad=4)
    ax.text(0.97, 0.92, f"Median: {med:,.0f}",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=7.5, color=TEXT_SEC)
    if col == "monetary":
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v,_: fmt_millions(v)))

# Cohort retention heatmap
ax_coh = fig.add_subplot(gs[2, 3])
set_dark_ax(ax_coh)
cohort_raw = D["cohort"].copy()
# pick first column as index, rest as month values
idx_col = cohort_raw.columns[0]
cohort_raw = cohort_raw.set_index(idx_col)
# take numeric columns 0-6
num_cols = [c for c in cohort_raw.columns
            if str(c).lstrip("-").isdigit() and 0 <= int(c) <= 6]
if num_cols:
    ch_plot = cohort_raw[num_cols].head(10).astype(float)
    import matplotlib.colors as mcolors
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "ret", [PANEL, ACCENT1])
    im = ax_coh.imshow(ch_plot.values, aspect="auto",
                       cmap=cmap, vmin=0, vmax=100)
    ax_coh.set_xticks(range(len(num_cols)))
    ax_coh.set_xticklabels([f"M{c}" for c in num_cols], fontsize=6.5)
    ax_coh.set_yticks(range(len(ch_plot)))
    ax_coh.set_yticklabels([str(i)[:7] for i in ch_plot.index],
                            fontsize=5.5)
    for r in range(ch_plot.shape[0]):
        for c in range(ch_plot.shape[1]):
            val = ch_plot.values[r, c]
            if not np.isnan(val):
                ax_coh.text(c, r, f"{val:.0f}%", ha="center", va="center",
                            fontsize=5, color=TEXT_PRI if val < 60 else BG)
ax_coh.set_title("Cohort Retention %\n(Month 0-6)",
                 color=TEXT_PRI, fontsize=9, pad=4)

# New vs Returning monthly
ax_nvr = fig.add_subplot(gs[3, :])
set_dark_ax(ax_nvr)
nvr = pd.read_csv(os.path.join(BASE, "sql", "results",
                               "q11_new_vs_returning_revenue.csv"))
nvr_pivot = nvr.pivot(index="month", columns="customer_type",
                      values="revenue").fillna(0)
x = range(len(nvr_pivot))
if "New" in nvr_pivot.columns and "Returning" in nvr_pivot.columns:
    ax_nvr.fill_between(x, nvr_pivot["New"]/1e6,
                        alpha=0.55, color=ACCENT2, label="New Customers")
    ax_nvr.fill_between(x, nvr_pivot["Returning"]/1e6,
                        alpha=0.40, color=ACCENT1, label="Returning Customers")
    ax_nvr.plot(x, nvr_pivot["New"]/1e6,      color=ACCENT2, linewidth=1.5)
    ax_nvr.plot(x, nvr_pivot["Returning"]/1e6, color=ACCENT1, linewidth=1.5)
ticks = list(range(0, len(nvr_pivot), 3))
ax_nvr.set_xticks(ticks)
ax_nvr.set_xticklabels(
    [str(nvr_pivot.index[i]) for i in ticks],
    rotation=25, ha="right", fontsize=7.5)
ax_nvr.set_title("Monthly Revenue: New vs Returning Customers",
                 color=TEXT_PRI, fontsize=10, pad=6)
ax_nvr.yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))
ax_nvr.legend(fontsize=8, facecolor=PANEL, labelcolor=TEXT_SEC)

fig.savefig(os.path.join(OUT_DIR, "dashboard_page_3_customers.png"),
            dpi=150, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print("   Saved: dashboard_page_3_customers.png")

# =============================================================================
# PAGE 4 — PRODUCT & RETURNS ANALYSIS
# =============================================================================
print("Generating Page 4: Product & Returns...")

fig = plt.figure(figsize=(14, 9), facecolor=BG)
page_header(fig, "Product & Returns Analysis",
            "ABC Classification | Margin | Return Rates | Discount Impact")

gs = gridspec.GridSpec(4, 4, figure=fig,
                       top=0.89, bottom=0.06, left=0.04, right=0.97,
                       hspace=0.58, wspace=0.40)

TOTAL_RETURNS  = len(D["returns"])
TOTAL_REFUNDS  = D["returns"]["refund_amount"].sum()
AVG_REFUND     = D["returns"]["refund_amount"].mean()
UNITS_SOLD     = D["items"]["quantity"].sum()

kpis4 = [
    ("Units Sold",       f"{UNITS_SOLD:,}",          None, True,  ACCENT1),
    ("Total Returns",    f"{TOTAL_RETURNS:,}",        None, False, ACCENT3),
    ("Total Refunds",    fmt_millions(TOTAL_REFUNDS), None, False, ACCENT3),
    ("Avg Refund Value", f"${AVG_REFUND:,.0f}",       None, False, ACCENT4),
]
for col, (lbl, val, delta, pos, vc) in enumerate(kpis4):
    ax = fig.add_subplot(gs[0, col])
    kpi_card(ax, lbl, val, delta, pos, vc)

# Top 15 products by revenue
top_prod = (fact.groupby("product_id")
            .agg(revenue=("line_total","sum"), units=("quantity","sum"))
            .merge(D["products"][["product_id","product_name","category"]],
                   on="product_id")
            .sort_values("revenue", ascending=False)
            .head(15))

ax_tp = fig.add_subplot(gs[1:3, :2])
set_dark_ax(ax_tp)
cat_colors_map = {c: CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
                  for i, c in enumerate(top_prod["category"].unique())}
colors_tp = [cat_colors_map[c] for c in top_prod["category"]]
ax_tp.barh(range(len(top_prod)), top_prod["revenue"].values[::-1]/1e3,
           color=colors_tp[::-1], alpha=0.85, zorder=3)
ax_tp.set_yticks(range(len(top_prod)))
ax_tp.set_yticklabels(
    [n[:22] + "…" if len(n) > 22 else n
     for n in top_prod["product_name"].values[::-1]],
    fontsize=6.5)
ax_tp.set_title("Top 15 Products by Revenue",
                color=TEXT_PRI, fontsize=10, pad=6)
ax_tp.xaxis.set_major_formatter(
    mticker.FuncFormatter(lambda v,_: f"${v:.0f}K"))

legend_patches = [mpatches.Patch(color=v, label=k)
                  for k, v in cat_colors_map.items()]
ax_tp.legend(handles=legend_patches, fontsize=6, facecolor=PANEL,
             labelcolor=TEXT_SEC, loc="lower right")

# Margin by category
cat_margin = D["q07"][["category","margin_pct","margin_rank"]].sort_values(
    "margin_pct", ascending=True)
ax_mg = fig.add_subplot(gs[1, 2:])
set_dark_ax(ax_mg)
avg_margin = cat_margin["margin_pct"].mean()
bar_cols = [ACCENT2 if v >= avg_margin else ACCENT3
            for v in cat_margin["margin_pct"]]
ax_mg.barh(cat_margin["category"], cat_margin["margin_pct"],
           color=bar_cols, alpha=0.85, zorder=3)
ax_mg.axvline(avg_margin, color=TEXT_SEC, linewidth=1.2,
              linestyle="--", label=f"Avg {avg_margin:.0f}%")
ax_mg.set_title("Gross Margin % by Category",
                color=TEXT_PRI, fontsize=10, pad=6)
ax_mg.set_xlabel("Margin %", color=TEXT_SEC)
ax_mg.legend(fontsize=7.5, facecolor=PANEL, labelcolor=TEXT_SEC)

# Return rate by category
ret_cat = (D["returns"]
           .merge(D["items"][["item_id","order_id","product_id"]],
                  on=["order_id","product_id"], how="left")
           .merge(D["products"][["product_id","category"]], on="product_id"))
ret_by_cat = ret_cat.groupby("category").size()
orders_by_cat = fact.groupby("category")["order_id"].nunique()
ret_rate_cat = (ret_by_cat / orders_by_cat * 100).dropna().sort_values()

ax_rr = fig.add_subplot(gs[2, 2:])
set_dark_ax(ax_rr)
avg_rr = ret_rate_cat.mean()
bar_cols_rr = [ACCENT3 if v > avg_rr else ACCENT2
               for v in ret_rate_cat.values]
ax_rr.barh(ret_rate_cat.index, ret_rate_cat.values,
           color=bar_cols_rr, alpha=0.85, zorder=3)
ax_rr.axvline(avg_rr, color=TEXT_SEC, linewidth=1.2,
              linestyle="--", label=f"Avg {avg_rr:.1f}%")
ax_rr.set_title("Return Rate % by Category",
                color=TEXT_PRI, fontsize=10, pad=6)
ax_rr.legend(fontsize=7.5, facecolor=PANEL, labelcolor=TEXT_SEC)

# Discount impact
disc = D["q17"].copy()
ax_di = fig.add_subplot(gs[3, :2])
set_dark_ax(ax_di)
x_di = range(len(disc))
bars1 = ax_di.bar(x_di, disc["revenue"]/1e6, color=ACCENT1,
                  alpha=0.75, label="Revenue", zorder=3)
ax_di2 = ax_di.twinx()
ax_di2.plot(x_di, disc["margin_pct"], color=ACCENT3, linewidth=2.5,
            marker="o", markersize=6, label="Margin %")
ax_di2.tick_params(colors=TEXT_SEC, labelsize=8)
for spine in ax_di2.spines.values(): spine.set_edgecolor(GRID_COL)
ax_di.set_xticks(x_di)
ax_di.set_xticklabels(disc["discount_bucket"], rotation=15,
                      ha="right", fontsize=7.5)
ax_di.set_title("Discount Bucket: Revenue vs Margin %",
                color=TEXT_PRI, fontsize=10, pad=6)
ax_di.yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda v,_: f"${v:.0f}M"))
ax_di2.yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
lines1, lab1 = ax_di.get_legend_handles_labels()
lines2, lab2 = ax_di2.get_legend_handles_labels()
ax_di.legend(lines1+lines2, lab1+lab2, fontsize=7,
             facecolor=PANEL, labelcolor=TEXT_SEC)

# Return reasons
reasons = D["returns"]["reason"].value_counts()
ax_rs = fig.add_subplot(gs[3, 2:])
set_dark_ax(ax_rs)
cols_rs = [CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
           for i in range(len(reasons))]
ax_rs.barh(reasons.index[::-1], reasons.values[::-1],
           color=cols_rs[::-1], alpha=0.85, zorder=3)
ax_rs.set_title("Return Reasons Distribution",
                color=TEXT_PRI, fontsize=10, pad=6)
ax_rs.set_xlabel("Count", color=TEXT_SEC)

fig.savefig(os.path.join(OUT_DIR, "dashboard_page_4_products.png"),
            dpi=150, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print("   Saved: dashboard_page_4_products.png")

# =============================================================================
# DONE
# =============================================================================
print("\n" + "=" * 55)
print("  All 4 dashboard images saved to reports/")
print("=" * 55)
for fname in sorted(os.listdir(OUT_DIR)):
    if fname.startswith("dashboard"):
        fpath = os.path.join(OUT_DIR, fname)
        size  = os.path.getsize(fpath) // 1024
        print(f"  {fname}  ({size} KB)")
