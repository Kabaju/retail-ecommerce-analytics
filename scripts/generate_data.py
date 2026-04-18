"""
=============================================================================
RETAIL & E-COMMERCE  PHASE 1: DATA GENERATION
=============================================================================
Purpose : Generate 5 interrelated, realistic retail tables with intentional
          data-quality issues (nulls, duplicates, outliers, casing, bad dates,
          currency mismatches) so Python cleaning is genuinely demonstrated.

Tables  : customers (10 000 rows)
          products  (500 SKUs, 8 categories)
          orders    (100 000 rows, 3 years)
          order_items (300 000 rows)
          returns   (8 000 rows)

Schema design philosophy (data-engineering reasoning):
  - Star schema:  orders + order_items form the fact tables; customers and
    products are dimensions.  returns hang off order_items for lineage.
  - Surrogate integer PKs everywhere  fast joins, simple FK constraints.
  - Dates stored as strings initially (ISO-8601) to let us inject malformed
    values that the cleaning step must fix.
  - Prices stored as floats with occasional wrong-currency symbols injected
    to simulate a real multi-region ingestion pipeline.

Skill demonstrated: Realistic synthetic data engineering, schema design,
                    deliberate data-quality embedding.
=============================================================================
"""

import random
import string
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta, date
import os
import warnings

warnings.filterwarnings("ignore")

#  Reproducibility 
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_US")
Faker.seed(SEED)

#  Output directory 
RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

#  Date range: 3 full years 
START_DATE = date(2022, 1, 1)
END_DATE   = date(2024, 12, 31)

def random_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))

def random_date_str(start: date, end: date, corrupt_pct: float = 0.0) -> str:
    """Return ISO date string; corrupt_pct fraction get mangled formats."""
    d = random_date(start, end)
    if random.random() < corrupt_pct:
        # Inject bad formats: MM/DD/YYYY, YYYY.MM.DD, plain garbage
        choice = random.randint(0, 2)
        if choice == 0:
            return d.strftime("%m/%d/%Y")        # US format
        elif choice == 1:
            return d.strftime("%Y.%m.%d")        # dot-separated
        else:
            return "".join(random.choices(string.digits + "-/", k=8))  # garbage
    return d.isoformat()

# =============================================================================
# TABLE 1  CUSTOMERS (10 000 rows)
# =============================================================================
print("  Generating customers ")

N_CUSTOMERS = 10_000

LOYALTY_TIERS   = ["Bronze", "Silver", "Gold", "Platinum"]
CHANNELS        = ["Online", "In-Store", "Mobile App", "Social Commerce"]
GENDERS         = ["Male", "Female", "Non-binary", "Prefer not to say"]
STATES          = [
    "CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI",
    "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
]

customers_rows = []
used_emails = set()

for i in range(1, N_CUSTOMERS + 1):
    first = fake.first_name()
    last  = fake.last_name()

    #  Intentional issue 1: inconsistent casing (10 %)
    if random.random() < 0.10:
        first = first.upper() if random.random() < 0.5 else first.lower()
        last  = last.upper()  if random.random() < 0.5 else last.lower()

    #  Intentional issue 2: duplicate emails (2 %)  same email, diff ID
    if random.random() < 0.02 and used_emails:
        email = random.choice(list(used_emails))
    else:
        email = fake.email()
        #  Intentional issue 3: malformed emails (1.5 %)
        if random.random() < 0.015:
            email = email.replace("@", "AT").replace(".", "DOT")
        used_emails.add(email)

    #  Intentional issue 4: nulls in optional fields (5 %)
    phone = fake.phone_number() if random.random() > 0.05 else None
    dob   = random_date(date(1950, 1, 1), date(2005, 12, 31)).isoformat() \
            if random.random() > 0.03 else None

    #  Intentional issue 5: outlier loyalty tier introduced via typo (0.5 %)
    if random.random() < 0.005:
        tier = random.choice(["GOLD", "silver", "Bronz", "Platinium"])
    else:
        tier = random.choices(
            LOYALTY_TIERS,
            weights=[0.40, 0.30, 0.20, 0.10],
        )[0]

    reg_date = random_date_str(START_DATE, END_DATE, corrupt_pct=0.02)

    customers_rows.append({
        "customer_id":       i,
        "first_name":        first,
        "last_name":         last,
        "email":             email,
        "phone":             phone,
        "gender":            random.choice(GENDERS) if random.random() > 0.02 else None,
        "date_of_birth":     dob,
        "registration_date": reg_date,
        "city":              fake.city(),
        "state":             random.choice(STATES),
        "country":           "US" if random.random() > 0.05 else random.choice(["USA", "us", "United States", "U.S."]),
        "postal_code":       fake.zipcode(),
        "loyalty_tier":      tier,
        "preferred_channel": random.choice(CHANNELS) if random.random() > 0.04 else None,
    })

customers_df = pd.DataFrame(customers_rows)

#  Intentional issue 6: inject ~50 fully duplicate rows
dup_indices = random.sample(range(len(customers_df)), 50)
dups = customers_df.iloc[dup_indices].copy()
customers_df = pd.concat([customers_df, dups], ignore_index=True)

customers_df.to_csv(os.path.join(RAW_DIR, "customers.csv"), index=False)
print(f"     customers.csv   {len(customers_df):,} rows  (incl. ~50 dupes)")

# =============================================================================
# TABLE 2  PRODUCTS (500 SKUs, 8 categories)
# =============================================================================
print("  Generating products ")

N_PRODUCTS = 500

CATEGORIES = {
    "Electronics":    ["Smartphones", "Laptops", "Headphones", "Tablets", "Cameras"],
    "Clothing":       ["Men's Apparel", "Women's Apparel", "Footwear", "Accessories"],
    "Home & Kitchen": ["Cookware", "Furniture", "Bedding", "Appliances"],
    "Sports":         ["Fitness Equipment", "Outdoor Gear", "Team Sports"],
    "Beauty":         ["Skincare", "Makeup", "Haircare", "Fragrances"],
    "Books":          ["Fiction", "Non-Fiction", "Academic", "Comics"],
    "Toys":           ["Board Games", "Action Figures", "Educational", "Outdoor Toys"],
    "Grocery":        ["Beverages", "Snacks", "Organic", "Dairy"],
}

BRANDS = ["NovaTech", "PureEdge", "UrbanNest", "SwiftGear", "GlowLab",
          "PageTurner", "PlayZone", "FreshCart", "ZenHome", "PeakForm",
          "LuxeWear", "ByteBox", "AromaBliss", "IronClad", "CloudWalker"]

# Realistic cost/price ranges per category
PRICE_RANGES = {
    "Electronics":    (50,  1500),
    "Clothing":       (10,   300),
    "Home & Kitchen": (15,   800),
    "Sports":         (20,   500),
    "Beauty":         (8,    200),
    "Books":          (5,     60),
    "Toys":           (10,   150),
    "Grocery":        (1,     40),
}

products_rows = []

for i in range(1, N_PRODUCTS + 1):
    cat  = random.choice(list(CATEGORIES.keys()))
    sub  = random.choice(CATEGORIES[cat])
    lo, hi = PRICE_RANGES[cat]
    cost  = round(random.uniform(lo * 0.4, hi * 0.6), 2)
    price = round(cost * random.uniform(1.2, 2.8), 2)

    #  Intentional issue 7: currency mismatch (3 %)  stored as string with symbol
    if random.random() < 0.03:
        price_val = random.choice([f"{price}", f"{price}", f"${price}", str(price) + " USD"])
    else:
        price_val = price

    #  Intentional issue 8: missing supplier (4 %)
    supplier_id = random.randint(1, 50) if random.random() > 0.04 else None

    #  Intentional issue 9: outlier price (0.5 %)  100 typo
    if random.random() < 0.005:
        price_val = price * 100

    #  Intentional issue 10: inconsistent product name casing (8 %)
    pname = f"{fake.word().title()} {sub} {random.choice(['Pro','Plus','Max','Lite','Ultra',''])}"
    if random.random() < 0.08:
        pname = pname.upper()

    products_rows.append({
        "product_id":     i,
        "sku":            f"SKU-{i:05d}",
        "product_name":   pname.strip(),
        "category":       cat,
        "sub_category":   sub,
        "brand":          random.choice(BRANDS),
        "unit_cost":      cost,
        "unit_price":     price_val,          # may be string with currency symbol
        "supplier_id":    supplier_id,
        "is_active":      random.choices([1, 0], weights=[0.90, 0.10])[0],
        "launch_date":    random_date_str(date(2018, 1, 1), END_DATE, corrupt_pct=0.015),
        "weight_kg":      round(random.uniform(0.1, 30.0), 2) if random.random() > 0.05 else None,
        "stock_quantity": random.randint(0, 5000) if random.random() > 0.03 else -random.randint(1, 50),  # negative = issue
    })

products_df = pd.DataFrame(products_rows)

#  Intentional issue 11: ~10 fully duplicate product rows
dup_p = random.sample(range(len(products_df)), 10)
products_df = pd.concat([products_df, products_df.iloc[dup_p]], ignore_index=True)

products_df.to_csv(os.path.join(RAW_DIR, "products.csv"), index=False)
print(f"     products.csv    {len(products_df):,} rows  (incl. ~10 dupes)")

# =============================================================================
# TABLE 3  ORDERS (100 000 rows, 3 years)
# =============================================================================
print("  Generating orders    (this takes ~30 s)")

N_ORDERS = 100_000

CHANNELS_ORDER   = ["Online", "In-Store", "Mobile App", "Social Commerce", "Wholesale"]
PAYMENT_METHODS  = ["Credit Card", "Debit Card", "PayPal", "Apple Pay", "Cash", "Gift Card", "BNPL"]
ORDER_STATUSES   = ["Completed", "Shipped", "Processing", "Cancelled", "Refunded", "On Hold"]
STATUS_WEIGHTS   = [0.65,       0.12,      0.08,        0.07,        0.05,       0.03]

valid_customer_ids = list(range(1, N_CUSTOMERS + 1))

orders_rows = []

for i in range(1, N_ORDERS + 1):
    order_date_obj = random_date(START_DATE, END_DATE)
    order_date_str = order_date_obj.isoformat()

    # Ship date 17 days after order; occasionally NULL (processing/cancelled)
    ship_days = random.randint(1, 7)
    ship_date_obj = order_date_obj + timedelta(days=ship_days)
    ship_date = ship_date_obj.isoformat() if random.random() > 0.12 else None

    # Delivery 310 days after ship; NULL if not shipped
    if ship_date:
        del_date_obj = ship_date_obj + timedelta(days=random.randint(3, 10))
        delivery_date = del_date_obj.isoformat() if random.random() > 0.08 else None
    else:
        delivery_date = None

    #  Intentional issue 12: ship_date before order_date (1 %)
    if random.random() < 0.01:
        ship_date = (order_date_obj - timedelta(days=random.randint(1, 5))).isoformat()

    #  Intentional issue 13: malformed order date (1.5 %)
    if random.random() < 0.015:
        order_date_str = order_date_obj.strftime("%m-%d-%Y")

    #  Intentional issue 14: NULL customer (0.5 %)  orphaned orders
    cust_id = random.choice(valid_customer_ids) if random.random() > 0.005 else None

    shipping_cost = round(random.uniform(0, 25), 2)
    discount      = round(random.uniform(0, 0.30) * random.uniform(50, 500), 2) if random.random() > 0.60 else 0.0

    #  Intentional issue 15: outlier shipping cost (0.3 %)  data entry error
    if random.random() < 0.003:
        shipping_cost = round(random.uniform(500, 9999), 2)

    orders_rows.append({
        "order_id":       i,
        "customer_id":    cust_id,
        "order_date":     order_date_str,
        "ship_date":      ship_date,
        "delivery_date":  delivery_date,
        "channel":        random.choice(CHANNELS_ORDER),
        "payment_method": random.choice(PAYMENT_METHODS),
        "shipping_cost":  shipping_cost,
        "discount_amount":discount,
        "status":         random.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS)[0],
        "city":           fake.city(),
        "state":          random.choice(STATES),
        "country":        "US" if random.random() > 0.04 else random.choice(["USA", "us", "United States"]),
    })

    if i % 20_000 == 0:
        print(f"       {i:,} / {N_ORDERS:,} orders generated")

orders_df = pd.DataFrame(orders_rows)

#  Intentional issue 16: ~200 duplicate order rows
dup_o = random.sample(range(len(orders_df)), 200)
orders_df = pd.concat([orders_df, orders_df.iloc[dup_o]], ignore_index=True)

orders_df.to_csv(os.path.join(RAW_DIR, "orders.csv"), index=False)
print(f"     orders.csv      {len(orders_df):,} rows  (incl. ~200 dupes)")

# =============================================================================
# TABLE 4  ORDER_ITEMS (300 000 rows)
# =============================================================================
print("  Generating order_items   (this takes ~45 s)")

N_ITEMS_TARGET = 300_000
valid_order_ids   = list(range(1, N_ORDERS + 1))
valid_product_ids = list(range(1, N_PRODUCTS + 1))

# Pre-build a product price lookup (use float where possible)
def safe_float(val):
    try:
        return float(str(val).replace("$","").replace("","").replace("","").replace(" USD",""))
    except:
        return None

product_prices = {
    row["product_id"]: safe_float(row["unit_price"])
    for _, row in products_df.drop_duplicates("product_id").iterrows()
}

items_rows = []
item_id    = 1

# Distribute items across orders using a Poisson-like draw (avg ~3 items/order)
orders_sample = random.choices(valid_order_ids, k=N_ITEMS_TARGET)

for order_id in orders_sample:
    prod_id = random.choice(valid_product_ids)
    qty     = random.choices([1, 2, 3, 4, 5, 6], weights=[0.45, 0.25, 0.15, 0.08, 0.05, 0.02])[0]

    base_price = product_prices.get(prod_id) or round(random.uniform(5, 500), 2)
    disc_pct   = round(random.uniform(0, 0.40), 4) if random.random() > 0.55 else 0.0
    line_total  = round(base_price * qty * (1 - disc_pct), 2)

    #  Intentional issue 17: negative quantity (0.4 %)  keyboard error
    if random.random() < 0.004:
        qty = -qty

    #  Intentional issue 18: NULL unit price (1 %)
    stored_price = base_price if random.random() > 0.01 else None

    #  Intentional issue 19: orphaned product_id (0.2 %)  references deleted product
    if random.random() < 0.002:
        prod_id = random.randint(N_PRODUCTS + 1, N_PRODUCTS + 50)

    items_rows.append({
        "item_id":     item_id,
        "order_id":    order_id,
        "product_id":  prod_id,
        "quantity":    qty,
        "unit_price":  stored_price,
        "discount_pct":disc_pct,
        "line_total":  line_total,
    })
    item_id += 1

    if item_id % 75_000 == 0:
        print(f"       {item_id:,} / {N_ITEMS_TARGET:,} items generated")

order_items_df = pd.DataFrame(items_rows)

#  Intentional issue 20: ~300 duplicate item rows
dup_it = random.sample(range(len(order_items_df)), 300)
order_items_df = pd.concat([order_items_df, order_items_df.iloc[dup_it]], ignore_index=True)

order_items_df.to_csv(os.path.join(RAW_DIR, "order_items.csv"), index=False)
print(f"     order_items.csv  {len(order_items_df):,} rows  (incl. ~300 dupes)")

# =============================================================================
# TABLE 5  RETURNS (8 000 rows)
# =============================================================================
print("  Generating returns ")

N_RETURNS = 8_000

RETURN_REASONS  = ["Defective", "Wrong Item", "Changed Mind", "Not As Described",
                   "Damaged in Transit", "Better Price Found", "Sizing Issue", "Other"]
RETURN_STATUSES = ["Approved", "Pending", "Rejected", "Completed"]
STATUS_W        = [0.50, 0.20, 0.10, 0.20]

# Returns must reference completed/refunded orders; approximate by sampling all order_ids
returnable_order_ids = list(range(1, N_ORDERS + 1))

returns_rows = []

for i in range(1, N_RETURNS + 1):
    order_id = random.choice(returnable_order_ids)

    # Return date must be after order date  approximate with a plausible offset
    base_date = random_date(START_DATE + timedelta(days=30), END_DATE)
    return_date_str = base_date.isoformat()

    #  Intentional issue 21: malformed return date (2 %)
    if random.random() < 0.02:
        return_date_str = base_date.strftime("%d %b %Y")   # "15 Mar 2023"

    refund = round(random.uniform(5, 800), 2)

    #  Intentional issue 22: outlier refund (0.3 %)  entry error
    if random.random() < 0.003:
        refund = round(random.uniform(10000, 99999), 2)

    #  Intentional issue 23: NULL return reason (6 %)
    reason = random.choice(RETURN_REASONS) if random.random() > 0.06 else None

    #  Intentional issue 24: return references non-existent product (1 %)
    prod_id = random.randint(1, N_PRODUCTS) if random.random() > 0.01 \
              else random.randint(N_PRODUCTS + 1, N_PRODUCTS + 100)

    returns_rows.append({
        "return_id":     i,
        "order_id":      order_id,
        "product_id":    prod_id,
        "return_date":   return_date_str,
        "reason":        reason,
        "refund_amount": refund,
        "status":        random.choices(RETURN_STATUSES, weights=STATUS_W)[0],
    })

returns_df = pd.DataFrame(returns_rows)

#  Intentional issue 25: ~80 duplicate return rows
dup_r = random.sample(range(len(returns_df)), 80)
returns_df = pd.concat([returns_df, returns_df.iloc[dup_r]], ignore_index=True)

returns_df.to_csv(os.path.join(RAW_DIR, "returns.csv"), index=False)
print(f"     returns.csv     {len(returns_df):,} rows  (incl. ~80 dupes)")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 65)
print("  PHASE 1 COMPLETE  Raw CSVs written to data/raw/")
print("=" * 65)
summary = {
    "Table":    ["customers", "products", "orders", "order_items", "returns"],
    "Rows":     [len(customers_df), len(products_df), len(orders_df),
                 len(order_items_df), len(returns_df)],
    "Columns":  [len(customers_df.columns), len(products_df.columns),
                 len(orders_df.columns),    len(order_items_df.columns),
                 len(returns_df.columns)],
}
print(pd.DataFrame(summary).to_string(index=False))
print()
