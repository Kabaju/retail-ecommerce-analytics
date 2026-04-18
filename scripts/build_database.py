# -*- coding: utf-8 -*-
"""
=============================================================================
RETAIL & E-COMMERCE -- PHASE 3: SQL DATABASE & ADVANCED ANALYTICS
=============================================================================
What this script does:
  1.  Creates a normalised SQLite database (retail.db) with PKs, FKs, indexes
  2.  Loads all 5 cleaned CSVs into the database
  3.  Executes 22 advanced SQL queries -- each answers a real business question
  4.  Saves every query result as a CSV in sql/results/ for Power BI

SQL skills demonstrated per query:
  Multi-table JOINs, CTEs, window functions (RANK, DENSE_RANK, LAG, LEAD,
  ROW_NUMBER, running SUM), subqueries, CASE logic, date manipulation
  (strftime), aggregations, CLV, rolling revenue, Top-N per partition,
  churn flagging, cohort revenue, discount impact, product affinity.

Why SQLite?
  Portable, zero-config, file-based -- any recruiter can open retail.db
  in DBeaver or DB Browser for SQLite and run the queries instantly.
  The same DDL translates directly to PostgreSQL / BigQuery with minor
  syntax changes (e.g. DATE_TRUNC instead of strftime).
=============================================================================
"""

import os, sqlite3, textwrap
import pandas as pd

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN_DIR   = os.path.join(BASE, "data", "cleaned")
SQL_DIR     = os.path.join(BASE, "sql")
RESULTS_DIR = os.path.join(SQL_DIR, "results")
DB_PATH     = os.path.join(SQL_DIR, "retail.db")
DDL_PATH    = os.path.join(SQL_DIR, "schema.sql")
QUERIES_PATH= os.path.join(SQL_DIR, "queries.sql")

for d in [SQL_DIR, RESULTS_DIR]:
    os.makedirs(d, exist_ok=True)

def section(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)

def log(msg):
    print(f"     {msg}")

# ---------------------------------------------------------------------------
# HELPER: run a query, print shape, save to CSV
# ---------------------------------------------------------------------------
def run_query(conn, query_name, sql, filename):
    try:
        df = pd.read_sql_query(sql, conn)
        path = os.path.join(RESULTS_DIR, filename)
        df.to_csv(path, index=False)
        log(f"[{query_name}]  {df.shape[0]:,} rows  -> sql/results/{filename}")
        return df
    except Exception as e:
        log(f"[{query_name}]  ERROR: {e}")
        return pd.DataFrame()

# =============================================================================
# 1.  DDL -- CREATE TABLES
# =============================================================================
section("1. CREATING DATABASE SCHEMA")

DDL = """
-- =============================================================
-- RETAIL & E-COMMERCE DATABASE SCHEMA
-- Engine   : SQLite 3
-- Pattern  : Star schema -- customers + products = dimensions,
--            orders + order_items = facts, returns = satellite
-- =============================================================

PRAGMA foreign_keys = OFF;

-- ── DIMENSION: customers ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    customer_id        INTEGER PRIMARY KEY,
    first_name         TEXT,
    last_name          TEXT,
    email              TEXT,
    phone              TEXT,
    gender             TEXT,
    date_of_birth      TEXT,
    registration_date  TEXT,
    city               TEXT,
    state              TEXT,
    country            TEXT    DEFAULT 'US',
    postal_code        TEXT,
    loyalty_tier       TEXT,   -- Bronze | Silver | Gold | Platinum
    preferred_channel  TEXT
);

-- ── DIMENSION: products ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    product_id     INTEGER PRIMARY KEY,
    sku            TEXT    NOT NULL UNIQUE,
    product_name   TEXT,
    category       TEXT,
    sub_category   TEXT,
    brand          TEXT,
    unit_cost      REAL,
    unit_price     REAL,
    supplier_id    INTEGER,
    is_active      INTEGER DEFAULT 1,
    launch_date    TEXT,
    weight_kg      REAL,
    stock_quantity INTEGER,
    margin_flag    INTEGER DEFAULT 0
);

-- ── FACT: orders ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    order_id         INTEGER PRIMARY KEY,
    customer_id      INTEGER,
    order_date       TEXT,
    ship_date        TEXT,
    delivery_date    TEXT,
    channel          TEXT,
    payment_method   TEXT,
    shipping_cost    REAL    DEFAULT 0,
    discount_amount  REAL    DEFAULT 0,
    status           TEXT,
    city             TEXT,
    state            TEXT,
    country          TEXT,
    order_year       INTEGER,
    order_month      TEXT,
    order_dow        TEXT,
    orphaned_order   INTEGER DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- ── FACT: order_items ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    item_id      INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL,
    product_id   INTEGER NOT NULL,
    quantity     INTEGER,
    unit_price   REAL,
    discount_pct REAL    DEFAULT 0,
    line_total   REAL,
    FOREIGN KEY (order_id)   REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- ── SATELLITE: returns ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS returns (
    return_id     INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    return_date   TEXT,
    reason        TEXT,
    refund_amount REAL,
    status        TEXT,
    FOREIGN KEY (order_id)   REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- ── INDEXES for JOIN and filter performance ───────────────────
CREATE INDEX IF NOT EXISTS idx_orders_customer    ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date        ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status      ON orders(status);
CREATE INDEX IF NOT EXISTS idx_items_order        ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product      ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_returns_order      ON returns(order_id);
CREATE INDEX IF NOT EXISTS idx_products_category  ON products(category);
"""

# Remove existing DB so we get a fresh schema on every run
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
# FK constraints documented in schema but not enforced at load time --
# orphaned rows were already flagged + validated in Phase 2 Python checks.
conn.execute("PRAGMA foreign_keys = OFF")
conn.executescript(DDL)
conn.commit()

with open(DDL_PATH, "w", encoding="utf-8") as f:
    f.write(DDL)

log("retail.db created with 5 tables + 7 indexes")
log("Schema saved to sql/schema.sql")

# =============================================================================
# 2.  LOAD CLEANED CSVs INTO DATABASE
# =============================================================================
section("2. LOADING CLEANED DATA INTO DATABASE")

# Helper: read CSV, coerce date columns to strings, drop extra cols
def load_table(csv_name, table_name, date_cols=None, drop_cols=None):
    path = os.path.join(CLEAN_DIR, csv_name)
    df = pd.read_csv(path, low_memory=False)

    # Drop derived/helper columns not in schema
    if drop_cols:
        df.drop(columns=[c for c in drop_cols if c in df.columns],
                inplace=True, errors="ignore")

    # Normalise date columns to ISO string YYYY-MM-DD (SQLite stores as TEXT)
    if date_cols:
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

    # SQLite INTEGER PK can't be NaN -- fill with 0 and let DB handle it
    df.to_sql(table_name, conn, if_exists="append", index=False,
              chunksize=500)
    log(f"Loaded {table_name:<15}  {len(df):>8,} rows")
    return df

load_table("customers_clean.csv",   "customers",
           date_cols=["date_of_birth","registration_date"])

load_table("products_clean.csv",    "products",
           date_cols=["launch_date"])

load_table("orders_clean.csv",      "orders",
           date_cols=["order_date","ship_date","delivery_date"],
           drop_cols=["order_month"])   # Period col -- recreated in SQL

load_table("order_items_clean.csv", "order_items")

load_table("returns_clean.csv",     "returns",
           date_cols=["return_date"])

conn.commit()
log("All tables loaded.")

# =============================================================================
# 3.  VERIFY ROW COUNTS
# =============================================================================
section("3. VERIFYING DATABASE CONTENTS")
for tbl in ["customers","products","orders","order_items","returns"]:
    cnt = pd.read_sql_query(f"SELECT COUNT(*) AS n FROM {tbl}", conn).iloc[0,0]
    log(f"{tbl:<15}  {cnt:>8,} rows in DB")

# =============================================================================
# 4.  ADVANCED QUERIES
# =============================================================================
section("4. RUNNING 22 ADVANCED SQL QUERIES")

# We accumulate all query SQL in a list to write to queries.sql at the end
all_queries = []

def Q(name, sql, filename):
    all_queries.append(f"-- {name}\n{sql.strip()}\n")
    return run_query(conn, name, sql, filename)

# ─────────────────────────────────────────────────────────────────────────────
# Q01  TOTAL REVENUE SUMMARY BY YEAR AND STATUS
# Business question: What is total revenue, profit, AOV, and order count
#                    broken down by year and status?
# Skills: aggregation, CASE, date function (strftime)
# ─────────────────────────────────────────────────────────────────────────────
Q("Q01 Revenue Summary by Year",
"""
SELECT
    strftime('%Y', o.order_date)          AS year,
    o.status,
    COUNT(DISTINCT o.order_id)            AS total_orders,
    ROUND(SUM(oi.line_total), 2)          AS gross_revenue,
    ROUND(SUM(oi.line_total - oi.quantity * p.unit_cost), 2) AS gross_profit,
    ROUND(AVG(oi.line_total), 2)          AS avg_line_value,
    ROUND(SUM(oi.line_total) /
          NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products    p  ON oi.product_id = p.product_id
WHERE o.order_date IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, gross_revenue DESC
""", "q01_revenue_summary_by_year.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q02  MONTHLY REVENUE WITH MOM GROWTH
# Business question: How does monthly revenue change month-over-month,
#                    and what is the growth rate?
# Skills: CTE, LAG window function, date arithmetic
# ─────────────────────────────────────────────────────────────────────────────
Q("Q02 Monthly Revenue MoM Growth",
"""
WITH monthly AS (
    SELECT
        strftime('%Y-%m', o.order_date)  AS month,
        ROUND(SUM(oi.line_total), 2)     AS revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status IN ('Completed','Shipped')
      AND o.order_date IS NOT NULL
    GROUP BY 1
)
SELECT
    month,
    revenue,
    LAG(revenue) OVER (ORDER BY month)                        AS prev_month_revenue,
    ROUND(revenue - LAG(revenue) OVER (ORDER BY month), 2)   AS mom_change,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY month))
        / NULLIF(LAG(revenue) OVER (ORDER BY month), 0) * 100
    , 2)                                                       AS mom_growth_pct
FROM monthly
ORDER BY month
""", "q02_monthly_revenue_mom.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q03  YEAR-OVER-YEAR REVENUE BY CATEGORY
# Business question: Which categories grew or shrank YoY?
# Skills: CTE, LEAD, conditional aggregation
# ─────────────────────────────────────────────────────────────────────────────
Q("Q03 YoY Revenue by Category",
"""
WITH yearly_cat AS (
    SELECT
        p.category,
        strftime('%Y', o.order_date)     AS year,
        ROUND(SUM(oi.line_total), 2)     AS revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products    p  ON oi.product_id = p.product_id
    WHERE o.status IN ('Completed','Shipped')
      AND o.order_date IS NOT NULL
    GROUP BY 1, 2
)
SELECT
    category,
    year,
    revenue,
    LAG(revenue) OVER (PARTITION BY category ORDER BY year) AS prev_year_revenue,
    ROUND(
        (revenue - LAG(revenue) OVER (PARTITION BY category ORDER BY year))
        / NULLIF(LAG(revenue) OVER (PARTITION BY category ORDER BY year), 0) * 100
    , 2) AS yoy_growth_pct
FROM yearly_cat
ORDER BY category, year
""", "q03_yoy_revenue_by_category.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q04  RUNNING TOTAL REVENUE (cumulative)
# Business question: What is the cumulative revenue milestone each month?
# Skills: SUM() OVER (ORDER BY) -- classic running total
# ─────────────────────────────────────────────────────────────────────────────
Q("Q04 Cumulative Revenue Running Total",
"""
WITH monthly AS (
    SELECT
        strftime('%Y-%m', o.order_date)  AS month,
        ROUND(SUM(oi.line_total), 2)     AS revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status IN ('Completed','Shipped')
      AND o.order_date IS NOT NULL
    GROUP BY 1
)
SELECT
    month,
    revenue,
    ROUND(SUM(revenue) OVER (ORDER BY month
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS cumulative_revenue,
    ROUND(AVG(revenue) OVER (ORDER BY month
          ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2)          AS rolling_3m_avg
FROM monthly
ORDER BY month
""", "q04_cumulative_revenue.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q05  ROLLING 30-DAY REVENUE
# Business question: What was the revenue for the 30 days ending each date?
# Skills: subquery correlated date filter, aggregation
# ─────────────────────────────────────────────────────────────────────────────
Q("Q05 Rolling 30-Day Revenue",
"""
WITH daily AS (
    SELECT
        DATE(o.order_date)           AS order_date,
        ROUND(SUM(oi.line_total), 2) AS daily_revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status IN ('Completed','Shipped')
      AND o.order_date IS NOT NULL
    GROUP BY 1
)
SELECT
    d.order_date,
    d.daily_revenue,
    ROUND(SUM(d2.daily_revenue), 2) AS rolling_30d_revenue
FROM daily d
JOIN daily d2
  ON d2.order_date BETWEEN DATE(d.order_date, '-29 days') AND d.order_date
GROUP BY d.order_date
ORDER BY d.order_date
""", "q05_rolling_30day_revenue.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q06  ROLLING 90-DAY REVENUE
# Business question: Smoothed quarterly revenue trend per day.
# Skills: correlated subquery, DATE() arithmetic
# ─────────────────────────────────────────────────────────────────────────────
Q("Q06 Rolling 90-Day Revenue",
"""
WITH daily AS (
    SELECT
        DATE(o.order_date)           AS order_date,
        ROUND(SUM(oi.line_total), 2) AS daily_revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status IN ('Completed','Shipped')
      AND o.order_date IS NOT NULL
    GROUP BY 1
)
SELECT
    d.order_date,
    d.daily_revenue,
    ROUND(SUM(d2.daily_revenue), 2) AS rolling_90d_revenue,
    COUNT(d2.order_date)            AS days_in_window
FROM daily d
JOIN daily d2
  ON d2.order_date BETWEEN DATE(d.order_date, '-89 days') AND d.order_date
GROUP BY d.order_date
ORDER BY d.order_date
""", "q06_rolling_90day_revenue.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q07  REVENUE & MARGIN RANK BY CATEGORY
# Business question: Which categories rank highest by revenue AND margin?
# Skills: RANK(), multiple window functions in one SELECT
# ─────────────────────────────────────────────────────────────────────────────
Q("Q07 Category Revenue and Margin Rank",
"""
WITH cat_metrics AS (
    SELECT
        p.category,
        ROUND(SUM(oi.line_total), 2)                               AS revenue,
        ROUND(SUM(oi.line_total - oi.quantity * p.unit_cost), 2)   AS gross_profit,
        ROUND(SUM(oi.line_total - oi.quantity * p.unit_cost)
              / NULLIF(SUM(oi.line_total), 0) * 100, 2)            AS margin_pct,
        COUNT(DISTINCT o.order_id)                                  AS total_orders
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products    p  ON oi.product_id = p.product_id
    WHERE o.status IN ('Completed','Shipped')
    GROUP BY 1
)
SELECT
    category,
    revenue,
    gross_profit,
    margin_pct,
    total_orders,
    RANK()       OVER (ORDER BY revenue      DESC) AS revenue_rank,
    RANK()       OVER (ORDER BY margin_pct   DESC) AS margin_rank,
    RANK()       OVER (ORDER BY total_orders DESC) AS volume_rank
FROM cat_metrics
ORDER BY revenue_rank
""", "q07_category_rank.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q08  TOP 5 PRODUCTS PER CATEGORY (revenue)
# Business question: What are the best-selling products in each category?
# Skills: DENSE_RANK() PARTITION BY, CTE filter on rank
# ─────────────────────────────────────────────────────────────────────────────
Q("Q08 Top 5 Products per Category",
"""
WITH product_rev AS (
    SELECT
        p.category,
        p.product_name,
        p.brand,
        ROUND(SUM(oi.line_total), 2)        AS revenue,
        SUM(oi.quantity)                     AS units_sold,
        COUNT(DISTINCT o.order_id)           AS order_count
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products    p  ON oi.product_id = p.product_id
    WHERE o.status IN ('Completed','Shipped')
    GROUP BY 1, 2, 3
),
ranked AS (
    SELECT *,
        DENSE_RANK() OVER (PARTITION BY category
                           ORDER BY revenue DESC) AS rank_in_category
    FROM product_rev
)
SELECT * FROM ranked
WHERE rank_in_category <= 5
ORDER BY category, rank_in_category
""", "q08_top5_products_per_category.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q09  CUSTOMER LIFETIME VALUE (CLV)
# Business question: What is each customer's total spend, order frequency,
#                    and lifetime value tier?
# Skills: multi-table JOIN, aggregation, CASE segmentation, subquery
# ─────────────────────────────────────────────────────────────────────────────
Q("Q09 Customer Lifetime Value",
"""
WITH clv AS (
    SELECT
        c.customer_id,
        c.first_name || ' ' || c.last_name       AS customer_name,
        c.loyalty_tier,
        c.state,
        COUNT(DISTINCT o.order_id)               AS total_orders,
        ROUND(SUM(oi.line_total), 2)             AS lifetime_value,
        ROUND(AVG(oi.line_total), 2)             AS avg_order_value,
        MIN(DATE(o.order_date))                  AS first_order_date,
        MAX(DATE(o.order_date))                  AS last_order_date,
        CAST(julianday(MAX(o.order_date))
             - julianday(MIN(o.order_date)) AS INTEGER) AS customer_tenure_days
    FROM customers c
    JOIN orders     o  ON c.customer_id  = o.customer_id
    JOIN order_items oi ON o.order_id    = oi.order_id
    WHERE o.status IN ('Completed','Shipped')
    GROUP BY 1, 2, 3, 4
)
SELECT *,
    CASE
        WHEN lifetime_value >= 500000 THEN 'VIP'
        WHEN lifetime_value >= 100000 THEN 'High Value'
        WHEN lifetime_value >= 20000  THEN 'Mid Value'
        ELSE                               'Low Value'
    END AS clv_segment
FROM clv
ORDER BY lifetime_value DESC
""", "q09_customer_lifetime_value.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q10  CHURN FLAGGING
# Business question: Which customers haven't ordered in the last 180 days
#                    (relative to the dataset end date 2024-12-31)?
# Skills: CTE, MAX aggregation, date comparison, CASE
# ─────────────────────────────────────────────────────────────────────────────
Q("Q10 Churn Flagging",
"""
WITH last_order AS (
    SELECT
        o.customer_id,
        MAX(DATE(o.order_date))   AS last_order_date,
        COUNT(DISTINCT o.order_id) AS total_orders
    FROM orders o
    WHERE o.status IN ('Completed','Shipped')
      AND o.customer_id IS NOT NULL
    GROUP BY 1
)
SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name  AS customer_name,
    c.loyalty_tier,
    c.state,
    lo.last_order_date,
    lo.total_orders,
    CAST(julianday('2024-12-31')
         - julianday(lo.last_order_date) AS INTEGER) AS days_since_last_order,
    CASE
        WHEN julianday('2024-12-31') - julianday(lo.last_order_date) > 180
             THEN 'Churned'
        WHEN julianday('2024-12-31') - julianday(lo.last_order_date) > 90
             THEN 'At Risk'
        ELSE 'Active'
    END AS churn_status
FROM customers c
JOIN last_order lo ON c.customer_id = lo.customer_id
ORDER BY days_since_last_order DESC
""", "q10_churn_flagging.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q11  NEW VS RETURNING CUSTOMER REVENUE PER MONTH
# Business question: How much of each month's revenue comes from new
#                    customers vs. returning customers?
# Skills: CTE chain, ROW_NUMBER(), CASE on row number
# ─────────────────────────────────────────────────────────────────────────────
Q("Q11 New vs Returning Customer Revenue",
"""
WITH first_orders AS (
    SELECT customer_id, MIN(DATE(order_date)) AS first_order_date
    FROM   orders
    WHERE  customer_id IS NOT NULL
    GROUP BY 1
),
order_type AS (
    SELECT
        o.order_id,
        o.customer_id,
        strftime('%Y-%m', o.order_date)  AS month,
        CASE WHEN DATE(o.order_date) = fo.first_order_date
             THEN 'New' ELSE 'Returning' END AS customer_type
    FROM orders o
    JOIN first_orders fo ON o.customer_id = fo.customer_id
    WHERE o.status IN ('Completed','Shipped')
      AND o.order_date IS NOT NULL
)
SELECT
    ot.month,
    ot.customer_type,
    COUNT(DISTINCT ot.order_id)          AS orders,
    COUNT(DISTINCT ot.customer_id)       AS customers,
    ROUND(SUM(oi.line_total), 2)         AS revenue
FROM order_type ot
JOIN order_items oi ON ot.order_id = oi.order_id
GROUP BY 1, 2
ORDER BY 1, 2
""", "q11_new_vs_returning_revenue.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q12  CHANNEL PERFORMANCE ANALYSIS
# Business question: Which sales channel drives the most revenue, highest
#                    AOV, and best margin?
# Skills: multi-table JOIN, aggregation, computed columns
# ─────────────────────────────────────────────────────────────────────────────
Q("Q12 Channel Performance",
"""
SELECT
    o.channel,
    COUNT(DISTINCT o.order_id)                               AS total_orders,
    COUNT(DISTINCT o.customer_id)                            AS unique_customers,
    ROUND(SUM(oi.line_total), 2)                             AS total_revenue,
    ROUND(SUM(oi.line_total) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value,
    ROUND(SUM(oi.line_total - oi.quantity * p.unit_cost), 2) AS gross_profit,
    ROUND(SUM(oi.line_total - oi.quantity * p.unit_cost)
          / NULLIF(SUM(oi.line_total), 0) * 100, 2)         AS margin_pct,
    ROUND(AVG(oi.discount_pct) * 100, 2)                    AS avg_discount_pct
FROM orders o
JOIN order_items oi ON o.order_id   = oi.order_id
JOIN products    p  ON oi.product_id = p.product_id
WHERE o.status IN ('Completed','Shipped')
GROUP BY 1
ORDER BY total_revenue DESC
""", "q12_channel_performance.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q13  AVERAGE ORDER VALUE TREND BY CHANNEL AND YEAR
# Business question: Is AOV growing per channel over the 3-year period?
# Skills: subquery aggregation, LEAD window
# ─────────────────────────────────────────────────────────────────────────────
Q("Q13 AOV by Channel and Year",
"""
WITH aov_data AS (
    SELECT
        o.channel,
        strftime('%Y', o.order_date)                          AS year,
        ROUND(SUM(oi.line_total) /
              NULLIF(COUNT(DISTINCT o.order_id),0), 2)        AS aov
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status IN ('Completed','Shipped')
      AND o.order_date IS NOT NULL
    GROUP BY 1, 2
)
SELECT
    channel,
    year,
    aov,
    LEAD(aov) OVER (PARTITION BY channel ORDER BY year) AS next_year_aov,
    ROUND(
        (LEAD(aov) OVER (PARTITION BY channel ORDER BY year) - aov)
        / NULLIF(aov, 0) * 100
    , 2) AS yoy_aov_change_pct
FROM aov_data
ORDER BY channel, year
""", "q13_aov_by_channel_year.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q14  RETURN RATE BY CATEGORY AND REASON
# Business question: Which category x reason combinations drive the most
#                    returns and refund cost?
# Skills: JOIN across 4 tables, aggregation, subquery for rate calc
# ─────────────────────────────────────────────────────────────────────────────
Q("Q14 Return Rate by Category and Reason",
"""
WITH completed_orders AS (
    SELECT p.category, COUNT(DISTINCT o.order_id) AS total_orders
    FROM orders o
    JOIN order_items oi ON o.order_id   = oi.order_id
    JOIN products    p  ON oi.product_id = p.product_id
    WHERE o.status IN ('Completed','Shipped')
    GROUP BY 1
)
SELECT
    p.category,
    r.reason,
    COUNT(r.return_id)                       AS return_count,
    ROUND(SUM(r.refund_amount), 2)           AS total_refund,
    ROUND(AVG(r.refund_amount), 2)           AS avg_refund,
    co.total_orders,
    ROUND(COUNT(r.return_id) * 100.0
          / NULLIF(co.total_orders, 0), 2)  AS return_rate_pct
FROM returns r
JOIN products p ON r.product_id = p.product_id
JOIN completed_orders co ON p.category = co.category
GROUP BY 1, 2, co.total_orders
ORDER BY return_count DESC
""", "q14_return_rate_by_category_reason.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q15  CUSTOMER ORDER FREQUENCY DISTRIBUTION
# Business question: Are most customers one-time buyers or repeat purchasers?
# Skills: subquery, CASE bucketing, COUNT aggregation
# ─────────────────────────────────────────────────────────────────────────────
Q("Q15 Order Frequency Distribution",
"""
WITH cust_freq AS (
    SELECT
        customer_id,
        COUNT(DISTINCT order_id) AS order_count
    FROM orders
    WHERE status IN ('Completed','Shipped')
      AND customer_id IS NOT NULL
    GROUP BY 1
)
SELECT
    CASE
        WHEN order_count = 1  THEN '1 order (one-time)'
        WHEN order_count <= 3 THEN '2-3 orders'
        WHEN order_count <= 6 THEN '4-6 orders'
        WHEN order_count <= 10 THEN '7-10 orders'
        ELSE '10+ orders (loyal)'
    END AS frequency_bucket,
    COUNT(*)                          AS customers,
    ROUND(AVG(order_count), 1)        AS avg_orders_in_bucket,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_customers
FROM cust_freq
GROUP BY 1
ORDER BY MIN(order_count)
""", "q15_order_frequency_distribution.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q16  TOP 20 CUSTOMERS BY LIFETIME VALUE
# Business question: Who are the top 20 highest-value customers?
# Skills: JOIN, aggregation, ORDER BY + LIMIT, ROW_NUMBER
# ─────────────────────────────────────────────────────────────────────────────
Q("Q16 Top 20 Customers by Revenue",
"""
SELECT
    ROW_NUMBER() OVER (ORDER BY SUM(oi.line_total) DESC) AS rank,
    c.customer_id,
    c.first_name || ' ' || c.last_name   AS customer_name,
    c.loyalty_tier,
    c.state,
    COUNT(DISTINCT o.order_id)           AS total_orders,
    ROUND(SUM(oi.line_total), 2)         AS lifetime_value,
    MIN(DATE(o.order_date))              AS first_order,
    MAX(DATE(o.order_date))              AS last_order
FROM customers c
JOIN orders      o  ON c.customer_id  = o.customer_id
JOIN order_items oi ON o.order_id     = oi.order_id
WHERE o.status IN ('Completed','Shipped')
GROUP BY c.customer_id, customer_name, c.loyalty_tier, c.state
ORDER BY lifetime_value DESC
LIMIT 20
""", "q16_top20_customers.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q17  DISCOUNT IMPACT ANALYSIS
# Business question: Do higher discounts drive more volume but less margin?
# Skills: CASE bucketing, aggregation, multiple metrics per bucket
# ─────────────────────────────────────────────────────────────────────────────
Q("Q17 Discount Impact Analysis",
"""
SELECT
    CASE
        WHEN oi.discount_pct = 0          THEN '0% (no discount)'
        WHEN oi.discount_pct <= 0.10      THEN '1-10%'
        WHEN oi.discount_pct <= 0.20      THEN '11-20%'
        WHEN oi.discount_pct <= 0.30      THEN '21-30%'
        ELSE                                   '31%+'
    END                                        AS discount_bucket,
    COUNT(oi.item_id)                          AS line_items,
    SUM(oi.quantity)                           AS units_sold,
    ROUND(SUM(oi.line_total), 2)               AS revenue,
    ROUND(SUM(oi.line_total - oi.quantity * p.unit_cost), 2)  AS gross_profit,
    ROUND(SUM(oi.line_total - oi.quantity * p.unit_cost)
          / NULLIF(SUM(oi.line_total), 0) * 100, 2)           AS margin_pct,
    ROUND(AVG(oi.line_total), 2)               AS avg_line_value
FROM order_items oi
JOIN orders   o ON oi.order_id   = o.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.status IN ('Completed','Shipped')
GROUP BY 1
ORDER BY MIN(oi.discount_pct)
""", "q17_discount_impact.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q18  COHORT REVENUE ANALYSIS
# Business question: How much revenue does each monthly cohort generate
#                    in each subsequent month?
# Skills: CTE chain, MIN aggregation for cohort assignment, strftime
# ─────────────────────────────────────────────────────────────────────────────
Q("Q18 Cohort Revenue",
"""
WITH cohorts AS (
    SELECT
        customer_id,
        strftime('%Y-%m', MIN(order_date)) AS cohort_month
    FROM orders
    WHERE customer_id IS NOT NULL
    GROUP BY 1
),
cohort_orders AS (
    SELECT
        c.cohort_month,
        strftime('%Y-%m', o.order_date)   AS order_month,
        CAST(
            (strftime('%Y', o.order_date) - strftime('%Y', c.cohort_month || '-01'))
            * 12
            + strftime('%m', o.order_date)
            - strftime('%m', c.cohort_month || '-01')
        AS INTEGER)                        AS month_index,
        SUM(oi.line_total)                 AS revenue,
        COUNT(DISTINCT o.customer_id)      AS active_customers
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN cohorts     c  ON o.customer_id = c.customer_id
    WHERE o.status IN ('Completed','Shipped')
      AND o.order_date IS NOT NULL
    GROUP BY 1, 2, 3
)
SELECT
    cohort_month,
    order_month,
    month_index,
    ROUND(revenue, 2)  AS cohort_revenue,
    active_customers
FROM cohort_orders
WHERE month_index BETWEEN 0 AND 12
ORDER BY cohort_month, month_index
""", "q18_cohort_revenue.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q19  REVENUE BY DAY OF WEEK AND HOUR PATTERN
# Business question: Which days of the week generate the most sales?
# Skills: strftime day extraction, aggregation, CASE for day name
# ─────────────────────────────────────────────────────────────────────────────
Q("Q19 Revenue by Day of Week",
"""
SELECT
    CASE strftime('%w', o.order_date)
        WHEN '0' THEN '7-Sunday'
        WHEN '1' THEN '1-Monday'
        WHEN '2' THEN '2-Tuesday'
        WHEN '3' THEN '3-Wednesday'
        WHEN '4' THEN '4-Thursday'
        WHEN '5' THEN '5-Friday'
        WHEN '6' THEN '6-Saturday'
    END                                       AS day_of_week,
    COUNT(DISTINCT o.order_id)                AS total_orders,
    ROUND(SUM(oi.line_total), 2)              AS total_revenue,
    ROUND(SUM(oi.line_total)
          / COUNT(DISTINCT o.order_id), 2)    AS avg_order_value
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status IN ('Completed','Shipped')
  AND o.order_date IS NOT NULL
GROUP BY 1
ORDER BY 1
""", "q19_revenue_by_day_of_week.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q20  PRODUCT AFFINITY (FREQUENTLY BOUGHT TOGETHER)
# Business question: Which product pairs are most commonly purchased
#                    in the same order? (market basket insight)
# Skills: self-join on order_items, aggregation, LIMIT
# ─────────────────────────────────────────────────────────────────────────────
Q("Q20 Product Affinity (Bought Together)",
"""
SELECT
    p1.product_name   AS product_a,
    p2.product_name   AS product_b,
    p1.category       AS category_a,
    p2.category       AS category_b,
    COUNT(*)          AS times_bought_together
FROM order_items oi1
JOIN order_items oi2 ON oi1.order_id   = oi2.order_id
                     AND oi1.product_id < oi2.product_id
JOIN products p1     ON oi1.product_id = p1.product_id
JOIN products p2     ON oi2.product_id = p2.product_id
GROUP BY 1, 2, 3, 4
ORDER BY times_bought_together DESC
LIMIT 30
""", "q20_product_affinity.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q21  LOYALTY TIER REVENUE AND MIGRATION SUMMARY
# Business question: Which loyalty tier drives the most revenue per customer?
# Skills: JOIN, aggregation, per-tier averages
# ─────────────────────────────────────────────────────────────────────────────
Q("Q21 Revenue by Loyalty Tier",
"""
SELECT
    COALESCE(c.loyalty_tier, 'Unknown')         AS loyalty_tier,
    COUNT(DISTINCT c.customer_id)               AS customers,
    COUNT(DISTINCT o.order_id)                  AS total_orders,
    ROUND(SUM(oi.line_total), 2)                AS total_revenue,
    ROUND(SUM(oi.line_total)
          / NULLIF(COUNT(DISTINCT c.customer_id),0), 2) AS revenue_per_customer,
    ROUND(SUM(oi.line_total)
          / NULLIF(COUNT(DISTINCT o.order_id),0), 2)    AS avg_order_value
FROM customers c
JOIN orders      o  ON c.customer_id  = o.customer_id
JOIN order_items oi ON o.order_id     = oi.order_id
WHERE o.status IN ('Completed','Shipped')
GROUP BY 1
ORDER BY revenue_per_customer DESC
""", "q21_revenue_by_loyalty_tier.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Q22  GEOGRAPHIC REVENUE HEAT MAP (STATE LEVEL)
# Business question: Which states generate the most revenue, orders, and
#                    customers — and what is the revenue per customer?
# Skills: JOIN, aggregation, computed per-customer ratio, RANK
# ─────────────────────────────────────────────────────────────────────────────
Q("Q22 Geographic Revenue by State",
"""
SELECT
    o.state,
    COUNT(DISTINCT o.order_id)                  AS total_orders,
    COUNT(DISTINCT o.customer_id)               AS unique_customers,
    ROUND(SUM(oi.line_total), 2)                AS total_revenue,
    ROUND(SUM(oi.line_total)
          / NULLIF(COUNT(DISTINCT o.customer_id), 0), 2) AS revenue_per_customer,
    ROUND(SUM(oi.line_total)
          / NULLIF(COUNT(DISTINCT o.order_id), 0), 2)    AS avg_order_value,
    RANK() OVER (ORDER BY SUM(oi.line_total) DESC)       AS revenue_rank
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status IN ('Completed','Shipped')
  AND o.state IS NOT NULL
GROUP BY 1
ORDER BY total_revenue DESC
""", "q22_geographic_revenue_by_state.csv")

# =============================================================================
# 5.  SAVE ALL QUERIES TO queries.sql
# =============================================================================
section("5. SAVING ALL QUERIES TO sql/queries.sql")

with open(QUERIES_PATH, "w", encoding="utf-8") as f:
    f.write("-- ============================================================\n")
    f.write("-- RETAIL & E-COMMERCE -- 22 ADVANCED SQL QUERIES\n")
    f.write("-- Database: sql/retail.db  (SQLite 3)\n")
    f.write("-- ============================================================\n\n")
    f.write("\n\n".join(all_queries))

log(f"Saved {len(all_queries)} queries to sql/queries.sql")

# =============================================================================
# 6.  FINAL SUMMARY
# =============================================================================
section("6. PHASE 3 COMPLETE -- SUMMARY")

result_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".csv")]
log(f"Database  : sql/retail.db")
log(f"Schema    : sql/schema.sql")
log(f"Queries   : sql/queries.sql  ({len(all_queries)} queries)")
log(f"Result CSVs: sql/results/    ({len(result_files)} files)")
print()
print("  Query results exported:")
for f in sorted(result_files):
    rows = len(pd.read_csv(os.path.join(RESULTS_DIR, f)))
    print(f"    {f:<55}  {rows:>6,} rows")

conn.close()
print()
print("=" * 65)
print("  PHASE 3 COMPLETE")
print("=" * 65)
