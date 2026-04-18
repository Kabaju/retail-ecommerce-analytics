# -*- coding: utf-8 -*-
"""
=============================================================================
RETAIL & E-COMMERCE -- PHASE 2: PROFESSIONAL DATA CLEANING & EDA
=============================================================================
Sections
  1.  Load raw CSVs + data quality audit (null counts, dupe counts, dtypes)
  2.  Clean: customers
  3.  Clean: products
  4.  Clean: orders
  5.  Clean: order_items
  6.  Clean: returns
  7.  Referential integrity checks across all tables
  8.  Export cleaned CSVs + text quality report
  9.  EDA -- Sales trends over time
  10. EDA -- Revenue by category / channel / region
  11. EDA -- Customer RFM segmentation
  12. EDA -- Return rate analysis
  13. EDA -- Cohort retention analysis
  14. Export EDA summary report

Skills demonstrated:
  pandas profiling, IQR + Z-score outlier detection, regex-based string
  cleaning, date normalisation with pd.to_datetime(errors='coerce'),
  referential integrity validation, RFM scoring, cohort pivot tables,
  publication-quality matplotlib/seaborn visualisations.
=============================================================================
"""

import os, re, sys, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend -- saves to PNG files
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from datetime import date

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR   = os.path.join(BASE, "data", "raw")
CLEAN_DIR = os.path.join(BASE, "data", "cleaned")
PLOTS_DIR = os.path.join(BASE, "reports", "plots")
REP_DIR   = os.path.join(BASE, "reports")
for d in [CLEAN_DIR, PLOTS_DIR, REP_DIR]:
    os.makedirs(d, exist_ok=True)

ANALYSIS_DATE = pd.Timestamp("2024-12-31")   # "today" for RFM recency calc

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def section(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)

def subsection(title):
    print(f"\n  -- {title}")

def save_fig(fig, name):
    path = os.path.join(PLOTS_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"     [PLOT] saved: reports/plots/{name}")

def iqr_bounds(series):
    """Return (lower, upper) IQR-based outlier fences (1.5 * IQR rule)."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr

def zscore_mask(series, threshold=3.0):
    """Boolean mask: True where |z-score| > threshold."""
    mu, sigma = series.mean(), series.std()
    if sigma == 0:
        return pd.Series(False, index=series.index)
    return ((series - mu).abs() / sigma) > threshold

# quality report lines accumulate here
quality_log = []

def log(msg):
    quality_log.append(msg)
    print(f"     {msg}")

# =============================================================================
# 1.  LOAD RAW DATA + AUDIT
# =============================================================================
section("1. LOADING RAW DATA + QUALITY AUDIT")

raw = {}
for tbl in ["customers", "products", "orders", "order_items", "returns"]:
    raw[tbl] = pd.read_csv(os.path.join(RAW_DIR, f"{tbl}.csv"), low_memory=False)
    print(f"  Loaded {tbl:15s}  shape={raw[tbl].shape}")

quality_log.append("=" * 65)
quality_log.append("RAW DATA QUALITY AUDIT")
quality_log.append("=" * 65)

for tbl, df in raw.items():
    quality_log.append(f"\n[{tbl.upper()}]  {df.shape[0]:,} rows x {df.shape[1]} cols")
    quality_log.append(f"  Duplicate rows : {df.duplicated().sum():,}")
    null_summary = df.isnull().sum()
    null_cols = null_summary[null_summary > 0]
    if len(null_cols):
        for col, cnt in null_cols.items():
            quality_log.append(f"  NULL  {col:<25s} {cnt:>6,}  ({cnt/len(df)*100:.1f}%)")
    else:
        quality_log.append("  No null values detected")

# =============================================================================
# 2.  CLEAN: CUSTOMERS
# =============================================================================
section("2. CLEANING: CUSTOMERS")

cust = raw["customers"].copy()
original_len = len(cust)

# -- 2a. Remove fully duplicate rows -----------------------------------------
# Justification: exact duplicates add zero information; safe to drop.
before = len(cust)
cust.drop_duplicates(inplace=True)
cust.reset_index(drop=True, inplace=True)
log(f"Duplicates removed (customers): {before - len(cust)}")

# -- 2b. Name casing: normalise to Title Case ---------------------------------
# Inconsistent casing makes GROUP BY on names wrong and dashboards look broken.
cust["first_name"] = cust["first_name"].str.strip().str.title()
cust["last_name"]  = cust["last_name"].str.strip().str.title()
log("Name casing normalised to Title Case")

# -- 2c. Email: fix malformed (AT -> @, DOT -> .) then lower-case -------------
# Email is used as a business key for deduplication and CRM joins.
cust["email"] = (cust["email"]
                 .str.replace(r"\bAT\b", "@", regex=True)
                 .str.replace(r"\bDOT\b", ".", regex=True)
                 .str.lower()
                 .str.strip())
# Flag still-invalid emails (no @ or no dot after @)
invalid_email_mask = ~cust["email"].str.match(r"^[^@]+@[^@]+\.[^@]+$", na=False)
log(f"Invalid emails flagged (kept, nulled): {invalid_email_mask.sum()}")
cust.loc[invalid_email_mask, "email"] = np.nan

# -- 2d. Deduplicate on email (keep first registration) ----------------------
# Duplicate emails across different customer_ids = data integrity violation.
before = len(cust)
cust.sort_values("customer_id", inplace=True)
cust.drop_duplicates(subset="email", keep="first", inplace=True)
cust.reset_index(drop=True, inplace=True)
log(f"Duplicate emails removed (kept earliest customer_id): {before - len(cust)}")

# -- 2e. Country: standardise variants to 'US' --------------------------------
country_map = {"USA": "US", "us": "US", "United States": "US", "U.S.": "US"}
cust["country"] = cust["country"].replace(country_map).str.strip()
log("Country variants normalised to 'US'")

# -- 2f. Loyalty tier: fix typos, standardise case ---------------------------
tier_map = {
    "GOLD": "Gold", "SILVER": "Silver", "BRONZE": "Bronze", "PLATINUM": "Platinum",
    "silver": "Silver", "Bronz": "Bronze", "Platinium": "Platinum",
    "gold": "Gold", "bronze": "Bronze", "platinum": "Platinum",
}
cust["loyalty_tier"] = cust["loyalty_tier"].replace(tier_map)
valid_tiers = {"Bronze", "Silver", "Gold", "Platinum"}
bad_tier_mask = ~cust["loyalty_tier"].isin(valid_tiers)
log(f"Unrecognised loyalty tiers set to NULL: {bad_tier_mask.sum()}")
cust.loc[bad_tier_mask, "loyalty_tier"] = np.nan

# -- 2g. Date: registration_date -- normalise mixed formats ------------------
# pd.to_datetime(errors='coerce') handles most
# variants; coerce turns unparseable garbage into NaT.
cust["registration_date"] = pd.to_datetime(
    cust["registration_date"], errors="coerce"
)
nat_reg = cust["registration_date"].isna().sum()
log(f"registration_date: {nat_reg} unparseable values set to NaT")

# -- 2h. Date: date_of_birth -------------------------------------------------
cust["date_of_birth"] = pd.to_datetime(
    cust["date_of_birth"], errors="coerce"
)

# -- 2i. Phone: strip to digits only, set too-short values to NULL -----------
cust["phone"] = cust["phone"].astype(str).str.replace(r"[^\d]", "", regex=True)
cust.loc[cust["phone"].str.len() < 7, "phone"] = np.nan
log("Phone cleaned to digits; too-short values nulled")

# -- 2j. Enforce dtypes ------------------------------------------------------
cust["customer_id"] = cust["customer_id"].astype(int)
cust["state"]       = cust["state"].str.strip().str.upper()
cust["postal_code"] = cust["postal_code"].astype(str).str.strip()

log(f"customers clean shape: {cust.shape}")

# =============================================================================
# 3.  CLEAN: PRODUCTS
# =============================================================================
section("3. CLEANING: PRODUCTS")

prod = raw["products"].copy()

# -- 3a. Duplicates ----------------------------------------------------------
before = len(prod)
prod.drop_duplicates(inplace=True)
prod.reset_index(drop=True, inplace=True)
log(f"Duplicates removed (products): {before - len(prod)}")

# -- 3b. unit_price: strip currency symbols, coerce to float -----------------
# Justification: any numeric aggregation on a mixed string/float column
# raises TypeError; we must extract the numeric value and log the loss.
def parse_price(val):
    if pd.isna(val):
        return np.nan
    cleaned = re.sub(r"[^\d\.]", "", str(val))
    try:
        return float(cleaned)
    except ValueError:
        return np.nan

prod["unit_price"] = prod["unit_price"].apply(parse_price)
prod["unit_cost"]  = pd.to_numeric(prod["unit_cost"], errors="coerce")
log("Currency symbols stripped from unit_price; coerced to float")

# -- 3c. Outlier prices (IQR method): cap rather than drop -------------------
# Why cap instead of drop? We want to keep the product row; the price is
# clearly a data-entry error (100x). Capping to the upper fence preserves
# the row while correcting the value.
lo, hi = iqr_bounds(prod["unit_price"].dropna())
outlier_price_mask = prod["unit_price"] > hi
log(f"Price outliers capped to IQR upper fence ({hi:.2f}): {outlier_price_mask.sum()} rows")
prod.loc[outlier_price_mask, "unit_price"] = hi

# Profit margin sanity: unit_price must be >= unit_cost
inverted_margin = prod["unit_price"] < prod["unit_cost"]
log(f"Rows where price < cost (flagged, not changed): {inverted_margin.sum()}")
prod["margin_flag"] = inverted_margin.astype(int)

# -- 3d. Negative stock_quantity: take absolute value ------------------------
neg_stock = prod["stock_quantity"] < 0
log(f"Negative stock_quantity corrected (abs): {neg_stock.sum()}")
prod["stock_quantity"] = prod["stock_quantity"].abs()

# -- 3e. Product name: title case --------------------------------------------
prod["product_name"] = prod["product_name"].str.strip().str.title()

# -- 3f. launch_date ---------------------------------------------------------
prod["launch_date"] = pd.to_datetime(
    prod["launch_date"], errors="coerce"
)

# -- 3g. weight_kg: impute NULLs with per-category median -------------------
# Dropping rows would shrink the product catalogue; median imputation by
# category respects the natural weight distribution (books vs. furniture).
prod["weight_kg"] = prod.groupby("category")["weight_kg"].transform(
    lambda s: s.fillna(s.median())
)
log("weight_kg NULLs imputed with per-category median")

prod["product_id"] = prod["product_id"].astype(int)
log(f"products clean shape: {prod.shape}")

# =============================================================================
# 4.  CLEAN: ORDERS
# =============================================================================
section("4. CLEANING: ORDERS")

orders = raw["orders"].copy()

# -- 4a. Duplicates ----------------------------------------------------------
before = len(orders)
orders.drop_duplicates(inplace=True)
orders.reset_index(drop=True, inplace=True)
log(f"Duplicates removed (orders): {before - len(orders)}")

# -- 4b. Parse all date columns ----------------------------------------------
for col in ["order_date", "ship_date", "delivery_date"]:
    orders[col] = pd.to_datetime(
        orders[col], errors="coerce"
    )
nat_order = orders["order_date"].isna().sum()
log(f"order_date: {nat_order} unparseable values set to NaT")

# -- 4c. Temporal logic: ship_date must be >= order_date --------------------
# A ship date before the order date is physically impossible and indicates
# a row-level data error. We null the ship date rather than drop the order.
bad_ship = orders["ship_date"] < orders["order_date"]
log(f"ship_date before order_date -> set to NaT: {bad_ship.sum()}")
orders.loc[bad_ship, "ship_date"]     = pd.NaT
orders.loc[bad_ship, "delivery_date"] = pd.NaT

# -- 4d. Outlier shipping_cost: IQR cap + Z-score flag ----------------------
# Z-score method: values with |z| > 3 are 3 standard deviations from mean --
# statistically extreme. We cap (not drop) because the order itself is valid.
orders["shipping_cost"] = pd.to_numeric(orders["shipping_cost"], errors="coerce").fillna(0)
lo, hi = iqr_bounds(orders["shipping_cost"])
z_mask  = zscore_mask(orders["shipping_cost"])
outlier_ship = (orders["shipping_cost"] > hi) | z_mask
log(f"Outlier shipping_cost capped to IQR upper fence ({hi:.2f}): {outlier_ship.sum()}")
orders.loc[outlier_ship, "shipping_cost"] = hi

# -- 4e. Country normalise ---------------------------------------------------
orders["country"] = orders["country"].replace(
    {"USA": "US", "us": "US", "United States": "US"}
).str.strip()

# -- 4f. NULL customer_id: keep rows, flag as orphaned ----------------------
# Dropping these orders would undercount revenue; flag instead for reporting.
orders["orphaned_order"] = orders["customer_id"].isna().astype(int)
log(f"Orders with NULL customer_id flagged as orphaned: {orders['orphaned_order'].sum()}")

# -- 4g. Derive helper columns -----------------------------------------------
orders["order_year"]  = orders["order_date"].dt.year
orders["order_month"] = orders["order_date"].dt.to_period("M")
orders["order_dow"]   = orders["order_date"].dt.day_name()

orders["order_id"]    = orders["order_id"].astype(int)
log(f"orders clean shape: {orders.shape}")

# =============================================================================
# 5.  CLEAN: ORDER_ITEMS
# =============================================================================
section("5. CLEANING: ORDER_ITEMS")

items = raw["order_items"].copy()

# -- 5a. Duplicates ----------------------------------------------------------
before = len(items)
items.drop_duplicates(inplace=True)
items.reset_index(drop=True, inplace=True)
log(f"Duplicates removed (order_items): {before - len(items)}")

# -- 5b. Negative quantity: abs() -------------------------------------------
neg_qty = items["quantity"] < 0
log(f"Negative quantities corrected (abs): {neg_qty.sum()}")
items["quantity"] = items["quantity"].abs()
items.loc[items["quantity"] == 0, "quantity"] = 1   # 0-qty line is nonsensical

# -- 5c. NULL unit_price: impute from products table ------------------------
# Use the cleaned products price lookup rather than dropping rows.
price_lookup = prod.set_index("product_id")["unit_price"].to_dict()
null_price = items["unit_price"].isna()
items.loc[null_price, "unit_price"] = items.loc[null_price, "product_id"].map(price_lookup)
still_null = items["unit_price"].isna().sum()
log(f"NULL unit_price imputed from products table; still null after imputation: {still_null}")

# -- 5d. Orphaned product_ids: flag and remove --------------------------------
valid_product_ids = set(prod["product_id"].unique())
orphan_prod = ~items["product_id"].isin(valid_product_ids)
log(f"order_items with orphaned product_id removed: {orphan_prod.sum()}")
items = items[~orphan_prod].copy()

# -- 5e. Recalculate line_total from clean values ----------------------------
# Ensure internal consistency: line_total = qty * unit_price * (1 - disc_pct)
items["discount_pct"] = items["discount_pct"].clip(0, 1).fillna(0)
items["line_total"]   = (items["quantity"] * items["unit_price"]
                         * (1 - items["discount_pct"])).round(2)

items["item_id"]   = range(1, len(items) + 1)
items["order_id"]  = items["order_id"].astype(int)
items["product_id"]= items["product_id"].astype(int)
log(f"order_items clean shape: {items.shape}")

# =============================================================================
# 6.  CLEAN: RETURNS
# =============================================================================
section("6. CLEANING: RETURNS")

rets = raw["returns"].copy()

# -- 6a. Duplicates ----------------------------------------------------------
before = len(rets)
rets.drop_duplicates(inplace=True)
rets.reset_index(drop=True, inplace=True)
log(f"Duplicates removed (returns): {before - len(rets)}")

# -- 6b. Parse return_date: handles "15 Mar 2023" and other formats ----------
rets["return_date"] = pd.to_datetime(
    rets["return_date"], errors="coerce"
)
log(f"return_date NaT after parsing: {rets['return_date'].isna().sum()}")

# -- 6c. Outlier refund_amount: IQR + Z-score cap ---------------------------
rets["refund_amount"] = pd.to_numeric(rets["refund_amount"], errors="coerce")
lo, hi = iqr_bounds(rets["refund_amount"].dropna())
z_mask = zscore_mask(rets["refund_amount"].dropna())
outlier_ref = rets["refund_amount"] > hi
log(f"Outlier refund_amount capped to IQR upper fence ({hi:.2f}): {outlier_ref.sum()}")
rets.loc[outlier_ref, "refund_amount"] = hi

# -- 6d. NULL reason: fill with 'Unknown' ------------------------------------
# Imputing with 'Unknown' (not dropping) preserves return count accuracy.
rets["reason"] = rets["reason"].fillna("Unknown")

# -- 6e. Orphaned product_ids ------------------------------------------------
orphan_ret = ~rets["product_id"].isin(valid_product_ids)
log(f"Returns with orphaned product_id removed: {orphan_ret.sum()}")
rets = rets[~orphan_ret].copy()

log(f"returns clean shape: {rets.shape}")

# =============================================================================
# 7.  REFERENTIAL INTEGRITY CHECKS
# =============================================================================
section("7. REFERENTIAL INTEGRITY CHECKS")

valid_order_ids    = set(orders["order_id"].unique())
valid_customer_ids = set(cust["customer_id"].unique())

# orders.customer_id -> customers
bad = orders["customer_id"].dropna()
bad = bad[~bad.isin(valid_customer_ids)]
log(f"orders.customer_id -> customers: {len(bad)} orphaned FKs (orphaned_order=1 rows excluded)")

# order_items.order_id -> orders
bad = items["order_id"][~items["order_id"].isin(valid_order_ids)]
log(f"order_items.order_id -> orders: {len(bad)} orphaned FKs")
items = items[items["order_id"].isin(valid_order_ids)].copy()

# returns.order_id -> orders
bad = rets["order_id"][~rets["order_id"].isin(valid_order_ids)]
log(f"returns.order_id -> orders: {len(bad)} orphaned FKs removed")
rets = rets[rets["order_id"].isin(valid_order_ids)].copy()

log("Referential integrity verified across all 5 tables")

# =============================================================================
# 8.  EXPORT CLEANED CSVs + QUALITY REPORT
# =============================================================================
section("8. EXPORTING CLEANED CSVs")

clean_tables = {
    "customers":   cust,
    "products":    prod,
    "orders":      orders,
    "order_items": items,
    "returns":     rets,
}

for name, df in clean_tables.items():
    path = os.path.join(CLEAN_DIR, f"{name}_clean.csv")
    df.to_csv(path, index=False)
    log(f"Saved data/cleaned/{name}_clean.csv  ({len(df):,} rows)")

# Write quality report
rep_path = os.path.join(REP_DIR, "data_quality_report.txt")
with open(rep_path, "w", encoding="utf-8") as f:
    f.write("RETAIL & E-COMMERCE -- DATA QUALITY REPORT\n")
    f.write(f"Generated: {date.today()}\n\n")
    f.write("\n".join(quality_log))
    f.write("\n\nCLEAN TABLE SHAPES\n")
    for name, df in clean_tables.items():
        f.write(f"  {name:<15} {df.shape[0]:>8,} rows  x  {df.shape[1]} cols\n")
print(f"\n  [REPORT] reports/data_quality_report.txt written")

# =============================================================================
# 9.  EDA -- BUILD MASTER FACT TABLE
# =============================================================================
section("9. EDA -- BUILDING MASTER FACT TABLE")

# Join order_items -> orders -> customers -> products
fact = (items
        .merge(orders[["order_id","customer_id","order_date","order_month",
                        "order_year","channel","status","state","country",
                        "shipping_cost","discount_amount","orphaned_order"]],
               on="order_id", how="left")
        .merge(cust[["customer_id","loyalty_tier","state"]],
               on="customer_id", how="left", suffixes=("_order","_cust"))
        .merge(prod[["product_id","product_name","category","sub_category",
                      "brand","unit_cost"]],
               on="product_id", how="left")
       )

# Only completed/shipped orders contribute to revenue reporting
revenue_statuses = {"Completed", "Shipped"}
fact_rev = fact[fact["status"].isin(revenue_statuses)].copy()

# Compute gross profit per line
fact_rev["unit_cost"] = fact_rev["unit_cost"].fillna(0)
fact_rev["gross_profit"] = fact_rev["line_total"] - (fact_rev["quantity"] * fact_rev["unit_cost"])

print(f"  Fact table (revenue rows): {len(fact_rev):,}")
print(f"  Total gross revenue: ${fact_rev['line_total'].sum():,.0f}")
print(f"  Total gross profit:  ${fact_rev['gross_profit'].sum():,.0f}")

# =============================================================================
# 10. EDA -- SALES TRENDS OVER TIME
# =============================================================================
section("10. EDA -- SALES TRENDS OVER TIME")

monthly = (fact_rev.groupby("order_month")
           .agg(revenue=("line_total","sum"), orders=("order_id","nunique"))
           .reset_index())
monthly["order_month_dt"] = monthly["order_month"].dt.to_timestamp()
monthly["revenue_3m_avg"] = monthly["revenue"].rolling(3, min_periods=1).mean()

# Plot 1: Monthly revenue + 3-month rolling average
fig, ax1 = plt.subplots(figsize=(14, 5))
ax1.bar(monthly["order_month_dt"], monthly["revenue"] / 1e6,
        color="#4C72B0", alpha=0.7, width=20, label="Monthly Revenue")
ax1.plot(monthly["order_month_dt"], monthly["revenue_3m_avg"] / 1e6,
         color="#DD8452", linewidth=2.5, label="3-Month Rolling Avg")
ax1.set_ylabel("Revenue (USD millions)")
ax1.set_xlabel("")
ax1.set_title("Monthly Revenue Trend (2022-2024) with 3-Month Rolling Average",
              fontsize=13, fontweight="bold")
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.1f}M"))
ax1.legend()
plt.xticks(rotation=30, fontsize=8)
fig.tight_layout()
save_fig(fig, "01_monthly_revenue_trend.png")

# Plot 2: Revenue by year (bar)
annual = fact_rev.groupby("order_year")["line_total"].sum().reset_index()
fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.bar(annual["order_year"].astype(str), annual["line_total"] / 1e6,
              color=["#4C72B0","#55A868","#C44E52"], edgecolor="white", width=0.5)
for bar, val in zip(bars, annual["line_total"]):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            f"${val/1e6:.1f}M", ha="center", va="bottom", fontsize=11, fontweight="bold")
ax.set_title("Annual Revenue (2022-2024)", fontsize=13, fontweight="bold")
ax.set_ylabel("Revenue (USD millions)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}M"))
fig.tight_layout()
save_fig(fig, "02_annual_revenue.png")

# Plot 3: Order volume by day of week
dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
dow_data = (orders[orders["status"].isin(revenue_statuses)]
            .groupby("order_dow")["order_id"].count()
            .reindex(dow_order))
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(dow_data.index, dow_data.values, color="#4C72B0", alpha=0.85)
ax.set_title("Order Volume by Day of Week", fontsize=13, fontweight="bold")
ax.set_ylabel("Number of Orders")
plt.xticks(rotation=20)
fig.tight_layout()
save_fig(fig, "03_orders_by_day_of_week.png")

print("  Sales trend plots saved.")

# =============================================================================
# 11. EDA -- REVENUE BY CATEGORY / CHANNEL / REGION
# =============================================================================
section("11. EDA -- REVENUE BY CATEGORY / CHANNEL / REGION")

# Plot 4: Revenue by category
cat_rev = (fact_rev.groupby("category")
           .agg(revenue=("line_total","sum"), profit=("gross_profit","sum"))
           .sort_values("revenue", ascending=True))
cat_rev["margin_pct"] = (cat_rev["profit"] / cat_rev["revenue"] * 100).round(1)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
# Revenue bar
axes[0].barh(cat_rev.index, cat_rev["revenue"] / 1e6, color="#4C72B0", alpha=0.85)
axes[0].set_xlabel("Revenue (USD millions)")
axes[0].set_title("Revenue by Category", fontsize=12, fontweight="bold")
axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}M"))
# Margin bar
colors = ["#55A868" if m >= 40 else "#C44E52" for m in cat_rev["margin_pct"]]
axes[1].barh(cat_rev.index, cat_rev["margin_pct"], color=colors, alpha=0.85)
axes[1].axvline(cat_rev["margin_pct"].mean(), color="black",
                linestyle="--", linewidth=1.2, label=f"Avg {cat_rev['margin_pct'].mean():.0f}%")
axes[1].set_xlabel("Gross Margin %")
axes[1].set_title("Gross Margin % by Category", fontsize=12, fontweight="bold")
axes[1].legend(fontsize=9)
fig.tight_layout()
save_fig(fig, "04_revenue_and_margin_by_category.png")

# Plot 5: Revenue by channel
channel_rev = (fact_rev.groupby("channel")["line_total"].sum()
               .sort_values(ascending=False))
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(channel_rev.index, channel_rev.values / 1e6,
       color=sns.color_palette("muted", len(channel_rev)), edgecolor="white")
ax.set_title("Revenue by Sales Channel", fontsize=13, fontweight="bold")
ax.set_ylabel("Revenue (USD millions)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}M"))
plt.xticks(rotation=15)
fig.tight_layout()
save_fig(fig, "05_revenue_by_channel.png")

# Plot 6: Top 10 states by revenue
state_rev = (fact_rev.groupby("state_order")["line_total"].sum()
             .sort_values(ascending=False).head(10))
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(state_rev.index, state_rev.values / 1e6, color="#4C72B0", alpha=0.85)
ax.set_title("Top 10 States by Revenue", fontsize=13, fontweight="bold")
ax.set_ylabel("Revenue (USD millions)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}M"))
fig.tight_layout()
save_fig(fig, "06_top10_states_revenue.png")

# Plot 7: Revenue share by category (pie)
cat_share = fact_rev.groupby("category")["line_total"].sum().sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(7, 7))
wedges, texts, autotexts = ax.pie(
    cat_share.values, labels=cat_share.index,
    autopct="%1.1f%%", startangle=140,
    colors=sns.color_palette("muted", len(cat_share)),
    pctdistance=0.82)
for t in autotexts:
    t.set_fontsize(9)
ax.set_title("Revenue Share by Category", fontsize=13, fontweight="bold")
fig.tight_layout()
save_fig(fig, "07_revenue_share_by_category_pie.png")

print("  Category/channel/region plots saved.")

# =============================================================================
# 12. EDA -- CUSTOMER RFM SEGMENTATION
# =============================================================================
section("12. EDA -- RFM SEGMENTATION")

# Build per-customer order summary (completed orders only)
cust_orders = (fact_rev.groupby("customer_id")
               .agg(
                   last_order_date=("order_date", "max"),
                   frequency=("order_id",          "nunique"),
                   monetary=("line_total",          "sum"),
               ).reset_index())

cust_orders["recency"] = (ANALYSIS_DATE - cust_orders["last_order_date"]).dt.days

# Score each dimension 1-5 using quintile binning
# Recency: lower days = better -> reverse the ranking
for col, asc in [("recency", True), ("frequency", False), ("monetary", False)]:
    label = col[0].upper()   # R, F, M
    try:
        cust_orders[f"{label}_score"] = pd.qcut(
            cust_orders[col], q=5,
            labels=[5,4,3,2,1] if asc else [1,2,3,4,5],
            duplicates="drop"
        ).astype(int)
    except Exception:
        cust_orders[f"{label}_score"] = 3   # fallback if qcut fails

cust_orders["RFM_score"] = (cust_orders["R_score"].astype(str)
                            + cust_orders["F_score"].astype(str)
                            + cust_orders["M_score"].astype(str))

# Segment mapping (industry-standard)
def rfm_segment(row):
    r, f, m = row["R_score"], row["F_score"], row["M_score"]
    avg = (r + f + m) / 3
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    elif r >= 3 and f >= 3 and m >= 4:
        return "Loyal Customers"
    elif r >= 4 and f <= 2:
        return "New Customers"
    elif r >= 3 and f >= 3 and m <= 3:
        return "Potential Loyalists"
    elif r <= 2 and f >= 3:
        return "At Risk"
    elif r == 1 and f >= 2:
        return "Lost"
    elif avg >= 3:
        return "Promising"
    else:
        return "Hibernating"

cust_orders["segment"] = cust_orders.apply(rfm_segment, axis=1)

seg_summary = (cust_orders.groupby("segment")
               .agg(customers=("customer_id","count"),
                    avg_revenue=("monetary","mean"),
                    total_revenue=("monetary","sum"))
               .sort_values("total_revenue", ascending=False))

print("\n  RFM Segment Summary:")
print(seg_summary.to_string())

# Plot 8: RFM segment distribution
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
segs = seg_summary.reset_index()
axes[0].barh(segs["segment"], segs["customers"],
             color=sns.color_palette("muted", len(segs)))
axes[0].set_title("Customers per RFM Segment", fontsize=12, fontweight="bold")
axes[0].set_xlabel("Number of Customers")

axes[1].barh(segs["segment"], segs["total_revenue"] / 1e6,
             color=sns.color_palette("muted", len(segs)))
axes[1].set_title("Revenue per RFM Segment", fontsize=12, fontweight="bold")
axes[1].set_xlabel("Total Revenue (USD millions)")
axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}M"))
fig.tight_layout()
save_fig(fig, "08_rfm_segments.png")

# Plot 9: RFM score distributions
fig, axes = plt.subplots(1, 3, figsize=(14, 4))
for ax, col, title, color in zip(
    axes,
    ["recency","frequency","monetary"],
    ["Recency (days since last order)","Frequency (orders)","Monetary (total spend $)"],
    ["#4C72B0","#55A868","#C44E52"]
):
    ax.hist(cust_orders[col], bins=40, color=color, alpha=0.8, edgecolor="white")
    ax.axvline(cust_orders[col].median(), color="black",
               linestyle="--", linewidth=1.5, label=f"Median: {cust_orders[col].median():.0f}")
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.legend(fontsize=8)
fig.suptitle("RFM Metric Distributions", fontsize=13, fontweight="bold", y=1.02)
fig.tight_layout()
save_fig(fig, "09_rfm_distributions.png")

# Export RFM table for Power BI
cust_orders.to_csv(os.path.join(CLEAN_DIR, "rfm_segments.csv"), index=False)
print("  rfm_segments.csv exported to data/cleaned/")

# =============================================================================
# 13. EDA -- RETURN RATE ANALYSIS
# =============================================================================
section("13. EDA -- RETURN RATE ANALYSIS")

# Return rate = returns / completed orders (by category)
ret_joined = (rets.merge(items[["item_id","order_id","product_id","line_total"]],
                         on=["order_id","product_id"], how="left")
                  .merge(prod[["product_id","category"]], on="product_id", how="left"))

returns_by_cat = ret_joined.groupby("category").size().rename("returns")
orders_by_cat  = (fact_rev.groupby("category")["order_id"]
                  .nunique().rename("orders"))
ret_rate = (pd.concat([returns_by_cat, orders_by_cat], axis=1)
            .dropna()
            .assign(return_rate=lambda d: d["returns"] / d["orders"] * 100)
            .sort_values("return_rate", ascending=False))

print("\n  Return Rate by Category:")
print(ret_rate.to_string())

# Plot 10: Return rate by category
fig, ax = plt.subplots(figsize=(10, 5))
colors = ["#C44E52" if v > ret_rate["return_rate"].mean() else "#4C72B0"
          for v in ret_rate["return_rate"]]
ax.barh(ret_rate.index, ret_rate["return_rate"], color=colors, alpha=0.85)
ax.axvline(ret_rate["return_rate"].mean(), color="black", linestyle="--",
           linewidth=1.5, label=f"Avg {ret_rate['return_rate'].mean():.1f}%")
ax.set_title("Return Rate by Category (%)", fontsize=13, fontweight="bold")
ax.set_xlabel("Return Rate (%)")
ax.legend()
fig.tight_layout()
save_fig(fig, "10_return_rate_by_category.png")

# Plot 11: Return reasons
reason_counts = rets["reason"].value_counts()
fig, ax = plt.subplots(figsize=(9, 4))
ax.barh(reason_counts.index, reason_counts.values,
        color=sns.color_palette("muted", len(reason_counts)))
ax.set_title("Return Reasons Distribution", fontsize=13, fontweight="bold")
ax.set_xlabel("Number of Returns")
fig.tight_layout()
save_fig(fig, "11_return_reasons.png")

# Plot 12: Monthly return rate trend
monthly_orders  = (orders[orders["status"].isin(revenue_statuses)]
                   .groupby("order_month")["order_id"].count())
monthly_returns = (rets.merge(orders[["order_id","order_month"]], on="order_id", how="left")
                   .groupby("order_month")["return_id"].count())
monthly_ret_rate = (monthly_returns / monthly_orders * 100).dropna().reset_index()
monthly_ret_rate.columns = ["order_month","return_rate"]
monthly_ret_rate["order_month_dt"] = monthly_ret_rate["order_month"].dt.to_timestamp()

fig, ax = plt.subplots(figsize=(13, 4))
ax.plot(monthly_ret_rate["order_month_dt"], monthly_ret_rate["return_rate"],
        color="#C44E52", linewidth=2, marker="o", markersize=3)
ax.axhline(monthly_ret_rate["return_rate"].mean(), color="black",
           linestyle="--", linewidth=1.2,
           label=f"Avg {monthly_ret_rate['return_rate'].mean():.1f}%")
ax.set_title("Monthly Return Rate Trend", fontsize=13, fontweight="bold")
ax.set_ylabel("Return Rate (%)")
ax.legend()
plt.xticks(rotation=30, fontsize=8)
fig.tight_layout()
save_fig(fig, "12_monthly_return_rate.png")

print("  Return rate plots saved.")

# =============================================================================
# 14. EDA -- COHORT RETENTION ANALYSIS
# =============================================================================
section("14. EDA -- COHORT RETENTION ANALYSIS")

# Cohort = the month a customer placed their FIRST order
# We then track how many of that cohort placed orders in each subsequent month.

cohort_df = (fact_rev[fact_rev["customer_id"].notna()]
             .groupby("customer_id")["order_month"]
             .min()
             .rename("cohort_month")
             .reset_index())

cohort_df = fact_rev.merge(cohort_df, on="customer_id", how="left")
# Compute cohort_index as integer month offset (robust across pandas versions)
def period_to_int(p):
    try:
        return int(p.year) * 12 + int(p.month)
    except Exception:
        return np.nan

cohort_df["_om_int"] = cohort_df["order_month"].apply(period_to_int)
cohort_df["_cm_int"] = cohort_df["cohort_month"].apply(period_to_int)
cohort_df["cohort_index"] = (cohort_df["_om_int"] - cohort_df["_cm_int"]).fillna(-1).astype(int)
cohort_df = cohort_df[cohort_df["cohort_index"] >= 0].copy()

# Pivot: rows = cohort month, cols = cohort index (0, 1, 2, ...)
cohort_pivot = (cohort_df.groupby(["cohort_month","cohort_index"])["customer_id"]
                .nunique()
                .unstack(fill_value=0))

# Limit to first 12 months and cohorts with enough data
cohort_pivot = cohort_pivot.loc[:, :12]

# Retention rate: divide each row by its cohort size (index 0)
cohort_size = cohort_pivot[0]
retention   = cohort_pivot.divide(cohort_size, axis=0).round(3) * 100

# Use only cohorts with >= 20 customers for statistical reliability
retention = retention[cohort_size >= 20]

# Plot 13: Cohort heatmap (top 18 cohorts for readability)
plot_ret = retention.head(18)
fig, ax = plt.subplots(figsize=(15, 8))
sns.heatmap(
    plot_ret.astype(float),
    ax=ax,
    annot=True, fmt=".0f",
    cmap="YlGn",
    linewidths=0.4,
    cbar_kws={"label": "Retention %"},
    mask=plot_ret.isna(),
)
ax.set_title("Monthly Cohort Retention (%) -- First 13 Months",
             fontsize=13, fontweight="bold")
ax.set_xlabel("Months Since First Order")
ax.set_ylabel("Cohort (First Order Month)")
ax.set_yticklabels([str(p) for p in plot_ret.index], rotation=0, fontsize=8)
fig.tight_layout()
save_fig(fig, "13_cohort_retention_heatmap.png")

# Average retention by cohort index
avg_ret = retention.mean(axis=0)
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(avg_ret.index, avg_ret.values, marker="o", color="#4C72B0",
        linewidth=2.5, markersize=6)
ax.fill_between(avg_ret.index, avg_ret.values, alpha=0.15, color="#4C72B0")
ax.set_title("Average Cohort Retention Curve", fontsize=13, fontweight="bold")
ax.set_xlabel("Months Since First Order")
ax.set_ylabel("Average Retention %")
ax.set_xticks(avg_ret.index)
fig.tight_layout()
save_fig(fig, "14_avg_cohort_retention_curve.png")

# Export cohort retention for Power BI
retention.reset_index().to_csv(
    os.path.join(CLEAN_DIR, "cohort_retention.csv"), index=False
)
print("  cohort_retention.csv exported to data/cleaned/")

# =============================================================================
# 15. EDA -- TOP PRODUCTS + PRICE DISTRIBUTIONS
# =============================================================================
section("15. EDA -- TOP PRODUCTS & PRICE DISTRIBUTION")

# Plot 14: Top 20 products by revenue
top20 = (fact_rev.groupby("product_name")["line_total"].sum()
         .sort_values(ascending=False).head(20))
fig, ax = plt.subplots(figsize=(10, 8))
ax.barh(top20.index[::-1], top20.values[::-1] / 1e3,
        color="#4C72B0", alpha=0.85)
ax.set_title("Top 20 Products by Revenue", fontsize=13, fontweight="bold")
ax.set_xlabel("Revenue (USD thousands)")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}K"))
fig.tight_layout()
save_fig(fig, "15_top20_products_revenue.png")

# Plot 15: Price distribution by category (box plot)
fig, ax = plt.subplots(figsize=(12, 5))
cat_order = prod.groupby("category")["unit_price"].median().sort_values().index
sns.boxplot(data=prod, x="category", y="unit_price", order=cat_order,
            palette="muted", ax=ax, fliersize=3)
ax.set_title("Unit Price Distribution by Category", fontsize=13, fontweight="bold")
ax.set_xlabel("")
ax.set_ylabel("Unit Price (USD)")
plt.xticks(rotation=20)
fig.tight_layout()
save_fig(fig, "16_price_distribution_by_category.png")

print("  Top products and price distribution plots saved.")

# =============================================================================
# 16. FINAL EDA SUMMARY REPORT
# =============================================================================
section("16. WRITING EDA SUMMARY REPORT")

total_revenue  = fact_rev["line_total"].sum()
total_profit   = fact_rev["gross_profit"].sum()
margin_pct     = total_profit / total_revenue * 100
total_orders   = orders[orders["status"].isin(revenue_statuses)]["order_id"].nunique()
total_customers= cust["customer_id"].nunique()
aov            = total_revenue / total_orders
return_rate_ov = len(rets) / total_orders * 100
top_cat        = cat_rev["revenue"].idxmax()
top_channel    = channel_rev.idxmax()
best_segment   = seg_summary["total_revenue"].idxmax()

report = f"""
RETAIL & E-COMMERCE -- EDA SUMMARY REPORT
Generated: {date.today()}
================================================================

BUSINESS OVERVIEW
-----------------
Total Revenue (2022-2024) : ${total_revenue:>14,.0f}
Total Gross Profit        : ${total_profit:>14,.0f}
Overall Gross Margin      : {margin_pct:>13.1f}%
Total Completed Orders    : {total_orders:>14,}
Unique Active Customers   : {total_customers:>14,}
Average Order Value (AOV) : ${aov:>14,.2f}
Overall Return Rate       : {return_rate_ov:>13.1f}%

TOP PERFORMERS
--------------
Top Revenue Category      : {top_cat}
Top Sales Channel         : {top_channel}
Highest-Value RFM Segment : {best_segment}
  Customers in segment    : {seg_summary.loc[best_segment,'customers']:,}
  Revenue from segment    : ${seg_summary.loc[best_segment,'total_revenue']:,.0f}

ANNUAL REVENUE BREAKDOWN
------------------------
"""
for _, row in annual.iterrows():
    report += f"  {int(row['order_year'])}  :  ${row['line_total']:>12,.0f}\n"

report += f"""
RFM SEGMENT BREAKDOWN
---------------------
"""
for seg, row in seg_summary.iterrows():
    report += (f"  {seg:<22}  customers: {row['customers']:>5,}  "
               f"  avg spend: ${row['avg_revenue']:>8,.0f}  "
               f"  total: ${row['total_revenue']:>12,.0f}\n")

report += f"""
RETURN RATES BY CATEGORY
------------------------
"""
for cat, row in ret_rate.iterrows():
    report += f"  {cat:<20}  {row['return_rate']:.1f}%\n"

report += f"""
PLOTS GENERATED (reports/plots/)
---------------------------------
  01_monthly_revenue_trend.png
  02_annual_revenue.png
  03_orders_by_day_of_week.png
  04_revenue_and_margin_by_category.png
  05_revenue_by_channel.png
  06_top10_states_revenue.png
  07_revenue_share_by_category_pie.png
  08_rfm_segments.png
  09_rfm_distributions.png
  10_return_rate_by_category.png
  11_return_reasons.png
  12_monthly_return_rate.png
  13_cohort_retention_heatmap.png
  14_avg_cohort_retention_curve.png
  15_top20_products_revenue.png
  16_price_distribution_by_category.png

CLEANED FILES EXPORTED (data/cleaned/)
---------------------------------------
  customers_clean.csv
  products_clean.csv
  orders_clean.csv
  order_items_clean.csv
  returns_clean.csv
  rfm_segments.csv
  cohort_retention.csv
"""

eda_path = os.path.join(REP_DIR, "eda_summary_report.txt")
with open(eda_path, "w", encoding="utf-8") as f:
    f.write(report)

print(report)
print("\n  [REPORT] reports/eda_summary_report.txt written")
print("\n" + "=" * 65)
print("  PHASE 2 COMPLETE")
print("=" * 65)
