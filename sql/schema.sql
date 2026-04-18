
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
