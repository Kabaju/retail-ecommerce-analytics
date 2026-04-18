-- ============================================================
-- RETAIL & E-COMMERCE -- 22 ADVANCED SQL QUERIES
-- Database: sql/retail.db  (SQLite 3)
-- ============================================================

-- Q01 Revenue Summary by Year
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


-- Q02 Monthly Revenue MoM Growth
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


-- Q03 YoY Revenue by Category
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


-- Q04 Cumulative Revenue Running Total
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


-- Q05 Rolling 30-Day Revenue
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


-- Q06 Rolling 90-Day Revenue
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


-- Q07 Category Revenue and Margin Rank
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


-- Q08 Top 5 Products per Category
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


-- Q09 Customer Lifetime Value
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


-- Q10 Churn Flagging
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


-- Q11 New vs Returning Customer Revenue
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


-- Q12 Channel Performance
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


-- Q13 AOV by Channel and Year
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


-- Q14 Return Rate by Category and Reason
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


-- Q15 Order Frequency Distribution
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


-- Q16 Top 20 Customers by Revenue
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


-- Q17 Discount Impact Analysis
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


-- Q18 Cohort Revenue
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


-- Q19 Revenue by Day of Week
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


-- Q20 Product Affinity (Bought Together)
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


-- Q21 Revenue by Loyalty Tier
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


-- Q22 Geographic Revenue by State
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
