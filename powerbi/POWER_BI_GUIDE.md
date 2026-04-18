# Power BI Setup Guide — Retail & E-Commerce Analytics Dashboard
## Phase 4: Complete Step-by-Step Instructions

---

## PART 1 — LOADING DATA INTO POWER BI

### Step 1: Open Power BI Desktop
- Launch Power BI Desktop
- Click **Get Data** → **Text/CSV**

### Step 2: Load these files in order (from your project folder)

Load each file via **Get Data → Text/CSV**. Use the exact filenames below.

| # | File | Folder | Table Name in Power BI |
|---|------|--------|------------------------|
| 1 | `orders_clean.csv` | `data/cleaned/` | `Orders` |
| 2 | `order_items_clean.csv` | `data/cleaned/` | `Order_Items` |
| 3 | `customers_clean.csv` | `data/cleaned/` | `Customers` |
| 4 | `products_clean.csv` | `data/cleaned/` | `Products` |
| 5 | `returns_clean.csv` | `data/cleaned/` | `Returns` |
| 6 | `rfm_segments.csv` | `data/cleaned/` | `RFM_Segments` |
| 7 | `q07_category_rank.csv` | `sql/results/` | `Category_Rank` |
| 8 | `q10_churn_flagging.csv` | `sql/results/` | `Churn_Flags` |
| 9 | `q15_order_frequency_distribution.csv` | `sql/results/` | `Order_Frequency` |
| 10 | `q17_discount_impact.csv` | `sql/results/` | `Discount_Impact` |
| 11 | `q22_geographic_revenue_by_state.csv` | `sql/results/` | `State_Revenue` |

### Step 3: Promote headers and set data types

For each table, in **Power Query Editor**:
1. Click **Transform** → **Use First Row as Headers** (if not already done)
2. Set these data types manually:

**Orders table:**
- `order_id` → Whole Number
- `customer_id` → Whole Number
- `order_date` → Date
- `ship_date` → Date
- `delivery_date` → Date
- `shipping_cost` → Decimal Number
- `discount_amount` → Decimal Number
- `order_year` → Whole Number

**Order_Items table:**
- `item_id`, `order_id`, `product_id`, `quantity` → Whole Number
- `unit_price`, `discount_pct`, `line_total` → Decimal Number

**Customers table:**
- `customer_id` → Whole Number
- `registration_date`, `date_of_birth` → Date

**Products table:**
- `product_id`, `supplier_id`, `stock_quantity` → Whole Number
- `unit_cost`, `unit_price`, `weight_kg` → Decimal Number

**Returns table:**
- `return_id`, `order_id`, `product_id` → Whole Number
- `return_date` → Date
- `refund_amount` → Decimal Number

### Step 4: Close and Apply
Click **Close & Apply** in Power Query Editor.

---

## PART 2 — BUILDING THE DATE DIMENSION TABLE

A dedicated Date table is essential for time intelligence DAX functions
(DATEADD, SAMEPERIODLASTYEAR, DATESYTD etc.). Create it in DAX:

1. Go to **Modeling** → **New Table**
2. Paste this DAX:

```dax
Date_Table =
VAR MinDate = MIN(Orders[order_date])
VAR MaxDate = MAX(Orders[order_date])
RETURN
ADDCOLUMNS(
    CALENDAR(MinDate, MaxDate),
    "Year",           YEAR([Date]),
    "Month Number",   MONTH([Date]),
    "Month Name",     FORMAT([Date], "MMMM"),
    "Month Short",    FORMAT([Date], "MMM"),
    "Quarter",        "Q" & QUARTER([Date]),
    "Year-Month",     FORMAT([Date], "YYYY-MM"),
    "Year-Quarter",   FORMAT([Date], "YYYY") & " Q" & QUARTER([Date]),
    "Day of Week",    WEEKDAY([Date], 2),
    "Day Name",       FORMAT([Date], "DDDD"),
    "Is Weekend",     IF(WEEKDAY([Date], 2) >= 6, "Weekend", "Weekday"),
    "Week Number",    WEEKNUM([Date])
)
```

3. After creating the table, go to **Modeling** → **Mark as Date Table**
   → select the `Date` column.

---

## PART 3 — BUILDING THE DATA MODEL (STAR SCHEMA)

### Step 1: Open Model View
Click the **Model** icon on the left sidebar (looks like three connected shapes).

### Step 2: Create these relationships

Go to **Manage Relationships** and create each one:

| From Table | From Column | To Table | To Column | Cardinality | Direction |
|------------|-------------|----------|-----------|-------------|-----------|
| `Order_Items` | `order_id` | `Orders` | `order_id` | Many-to-One | Single |
| `Order_Items` | `product_id` | `Products` | `product_id` | Many-to-One | Single |
| `Orders` | `customer_id` | `Customers` | `customer_id` | Many-to-One | Single |
| `Orders` | `order_date` | `Date_Table` | `Date` | Many-to-One | Single |
| `Returns` | `order_id` | `Orders` | `order_id` | Many-to-One | Single |
| `Returns` | `product_id` | `Products` | `product_id` | Many-to-One | Single |
| `RFM_Segments` | `customer_id` | `Customers` | `customer_id` | One-to-One | Single |

### Step 3: Verify model layout
Your model should look like this:

```
                    Date_Table
                        |
                        | (order_date)
                        |
  Customers -------- Orders -------- Order_Items -------- Products
      |                  |
  RFM_Segments        Returns
```

This is a **star schema**: `Order_Items` is the central fact table,
all others are dimensions or satellite facts. Slicers on any dimension
automatically filter the fact table through the relationships.

---

## PART 4 — CREATING A MEASURES TABLE

Best practice: keep all DAX measures in a dedicated empty table.

1. **Modeling** → **Enter Data**
2. Name it `_Measures`, add one blank column, click **Load**
3. Right-click the table → **Hide** (it won't appear in report view)
4. Create all measures inside this table

---

## PART 5 — 35 DAX MEASURES

See `dax_measures.dax` for copy-paste-ready code.
Below is each measure with full explanation.

---

### SECTION A: Revenue & Profit (8 measures)

---

#### M01 — Total Revenue
```dax
Total Revenue =
SUMX(
    Order_Items,
    Order_Items[line_total]
)
```
**Why SUMX not SUM:** SUMX iterates row-by-row, making it filter-context aware.
SUM would also work here since line_total is pre-calculated, but SUMX is the
safer pattern for any computed column or expression.

---

#### M02 — Total Cost
```dax
Total Cost =
SUMX(
    Order_Items,
    Order_Items[quantity] * RELATED(Products[unit_cost])
)
```
**RELATED()** traverses the relationship from Order_Items to Products to fetch
unit_cost for each row — equivalent to a SQL JOIN.

---

#### M03 — Gross Profit
```dax
Gross Profit =
[Total Revenue] - [Total Cost]
```

---

#### M04 — Profit Margin %
```dax
Profit Margin % =
DIVIDE(
    [Gross Profit],
    [Total Revenue],
    0
)
```
**DIVIDE vs `/`:** DIVIDE handles division by zero gracefully (returns the
third argument, 0) instead of throwing an error. Always use DIVIDE.

---

#### M05 — Total Discount Given
```dax
Total Discount Given =
SUMX(
    Order_Items,
    Order_Items[quantity] * Order_Items[unit_price] * Order_Items[discount_pct]
)
```

---

#### M06 — Average Order Value (AOV)
```dax
Average Order Value =
DIVIDE(
    [Total Revenue],
    DISTINCTCOUNT(Orders[order_id]),
    0
)
```

---

#### M07 — Revenue per Customer
```dax
Revenue per Customer =
DIVIDE(
    [Total Revenue],
    DISTINCTCOUNT(Orders[customer_id]),
    0
)
```

---

#### M08 — Revenue per Unit Sold
```dax
Revenue per Unit Sold =
DIVIDE(
    [Total Revenue],
    SUM(Order_Items[quantity]),
    0
)
```

---

### SECTION B: Order & Volume Metrics (4 measures)

---

#### M09 — Total Orders
```dax
Total Orders =
DISTINCTCOUNT(Orders[order_id])
```

---

#### M10 — Units Sold
```dax
Units Sold =
SUM(Order_Items[quantity])
```

---

#### M11 — Completed Orders
```dax
Completed Orders =
CALCULATE(
    DISTINCTCOUNT(Orders[order_id]),
    Orders[status] IN {"Completed", "Shipped"}
)
```
**CALCULATE** modifies the filter context. Here it adds a filter on status,
counting only revenue-generating orders regardless of what slicers are active.

---

#### M12 — Avg Items per Order
```dax
Avg Items per Order =
DIVIDE(
    SUM(Order_Items[quantity]),
    DISTINCTCOUNT(Order_Items[order_id]),
    0
)
```

---

### SECTION C: Time Intelligence — Growth (6 measures)

---

#### M13 — Revenue Previous Month
```dax
Revenue Previous Month =
CALCULATE(
    [Total Revenue],
    DATEADD(Date_Table[Date], -1, MONTH)
)
```
**DATEADD** shifts the current date context by -1 month. This is why having
a proper Date_Table marked as a date table is required.

---

#### M14 — MoM Revenue Change
```dax
MoM Revenue Change =
[Total Revenue] - [Revenue Previous Month]
```

---

#### M15 — MoM Revenue Growth %
```dax
MoM Revenue Growth % =
DIVIDE(
    [MoM Revenue Change],
    [Revenue Previous Month],
    BLANK()
)
```
Returns BLANK() (not 0) when there's no prior month — this prevents misleading
100% growth on the first data point.

---

#### M16 — Revenue Same Period Last Year
```dax
Revenue SPLY =
CALCULATE(
    [Total Revenue],
    SAMEPERIODLASTYEAR(Date_Table[Date])
)
```

---

#### M17 — YoY Revenue Growth %
```dax
YoY Revenue Growth % =
DIVIDE(
    [Total Revenue] - [Revenue SPLY],
    [Revenue SPLY],
    BLANK()
)
```

---

#### M18 — Revenue Year-to-Date
```dax
Revenue YTD =
TOTALYTD(
    [Total Revenue],
    Date_Table[Date]
)
```

---

### SECTION D: Rolling Window Revenue (4 measures)

---

#### M19 — Rolling 3-Month Revenue
```dax
Rolling 3M Revenue =
CALCULATE(
    [Total Revenue],
    DATESINPERIOD(
        Date_Table[Date],
        LASTDATE(Date_Table[Date]),
        -3,
        MONTH
    )
)
```
**DATESINPERIOD** creates a dynamic date range ending on the last visible date.
This gives a true trailing 3-month window that responds to slicer selection.

---

#### M20 — Rolling 12-Month Revenue
```dax
Rolling 12M Revenue =
CALCULATE(
    [Total Revenue],
    DATESINPERIOD(
        Date_Table[Date],
        LASTDATE(Date_Table[Date]),
        -12,
        MONTH
    )
)
```

---

#### M21 — Rolling 3M Profit Margin %
```dax
Rolling 3M Profit Margin % =
DIVIDE(
    CALCULATE(
        [Gross Profit],
        DATESINPERIOD(Date_Table[Date], LASTDATE(Date_Table[Date]), -3, MONTH)
    ),
    CALCULATE(
        [Total Revenue],
        DATESINPERIOD(Date_Table[Date], LASTDATE(Date_Table[Date]), -3, MONTH)
    ),
    0
)
```

---

#### M22 — Revenue vs Rolling 12M Average
```dax
Revenue vs 12M Avg =
[Total Revenue] - DIVIDE([Rolling 12M Revenue], 12, 0)
```

---

### SECTION E: Customer Intelligence (5 measures)

---

#### M23 — Total Customers
```dax
Total Customers =
DISTINCTCOUNT(Customers[customer_id])
```

---

#### M24 — Active Customers (last 90 days)
```dax
Active Customers =
CALCULATE(
    DISTINCTCOUNT(Orders[customer_id]),
    DATESINPERIOD(
        Date_Table[Date],
        LASTDATE(Date_Table[Date]),
        -90,
        DAY
    ),
    Orders[status] IN {"Completed", "Shipped"}
)
```

---

#### M25 — New Customers This Period
```dax
New Customers =
VAR CurrentPeriodCustomers =
    CALCULATETABLE(
        VALUES(Orders[customer_id]),
        ALLEXCEPT(Date_Table, Date_Table[Year], Date_Table[Month Number])
    )
VAR FirstOrderDates =
    CALCULATETABLE(
        ADDCOLUMNS(
            VALUES(Orders[customer_id]),
            "FirstOrder", CALCULATE(MIN(Orders[order_date]))
        ),
        ALL(Date_Table)
    )
RETURN
    COUNTROWS(
        FILTER(
            FirstOrderDates,
            MONTH([FirstOrder]) = SELECTEDVALUE(Date_Table[Month Number]) &&
            YEAR([FirstOrder]) = SELECTEDVALUE(Date_Table[Year])
        )
    )
```

---

#### M26 — Average Customer Lifetime Value
```dax
Avg Customer Lifetime Value =
DIVIDE(
    [Total Revenue],
    [Total Customers],
    0
)
```

---

#### M27 — Customer Retention Rate (from RFM)
```dax
Customer Retention Rate =
DIVIDE(
    CALCULATE(
        COUNTROWS(RFM_Segments),
        RFM_Segments[frequency] > 1
    ),
    COUNTROWS(RFM_Segments),
    0
)
```

---

### SECTION F: Returns Analysis (3 measures)

---

#### M28 — Total Returns
```dax
Total Returns =
COUNTROWS(Returns)
```

---

#### M29 — Return Rate %
```dax
Return Rate % =
DIVIDE(
    [Total Returns],
    [Completed Orders],
    0
)
```

---

#### M30 — Total Refund Amount
```dax
Total Refund Amount =
SUM(Returns[refund_amount])
```

---

### SECTION G: Advanced & Dynamic Measures (5 measures)

---

#### M31 — Dynamic ABC Product Classification (Calculated Column)

Add this as a **calculated column** on the Products table:

```dax
ABC Class =
VAR ProductRevenue =
    CALCULATE(
        SUM(Order_Items[line_total]),
        ALLEXCEPT(Products, Products[product_id])
    )
VAR TotalRevenue =
    CALCULATE(SUM(Order_Items[line_total]), ALL(Products))
VAR RunningPct =
    DIVIDE(
        SUMX(
            FILTER(
                ALL(Products),
                CALCULATE(SUM(Order_Items[line_total]),
                           ALLEXCEPT(Products, Products[product_id]))
                >= ProductRevenue
            ),
            CALCULATE(SUM(Order_Items[line_total]),
                      ALLEXCEPT(Products, Products[product_id]))
        ),
        TotalRevenue,
        0
    )
RETURN
    SWITCH(
        TRUE(),
        RunningPct <= 0.80, "A — Top 80% Revenue",
        RunningPct <= 0.95, "B — Next 15% Revenue",
        "C — Bottom 5% Revenue"
    )
```
**Why ABC classification matters:** Class A products are your critical SKUs —
stockouts here are catastrophic. Class C products may be candidates for
discontinuation. This is a standard supply-chain inventory segmentation.

---

#### M32 — What-If: Discount Scenario Revenue Impact

First, create a **What-If Parameter**:
1. **Modeling** → **New Parameter** → **Numeric range**
2. Name: `Discount Adjustment %`
3. Min: -20, Max: 20, Increment: 1, Default: 0
4. This auto-creates a slicer and a `Discount Adjustment %[Discount Adjustment % Value]` measure

Then create this measure:
```dax
What-If Revenue Impact =
VAR AdjustmentFactor = 1 + ([Discount Adjustment % Value] / 100)
VAR AdjustedRevenue =
    SUMX(
        Order_Items,
        Order_Items[line_total] * AdjustmentFactor
    )
RETURN
    AdjustedRevenue - [Total Revenue]
```

---

#### M33 — Selected Category Revenue Share %
```dax
Category Revenue Share % =
DIVIDE(
    [Total Revenue],
    CALCULATE([Total Revenue], ALL(Products[category])),
    0
)
```
**ALL()** removes the category filter to get the grand total, making the
result a true share regardless of what category is selected.

---

#### M34 — RFM Segment Revenue Share %
```dax
RFM Segment Revenue Share % =
DIVIDE(
    [Total Revenue],
    CALCULATE([Total Revenue], ALL(RFM_Segments[segment])),
    0
)
```

---

#### M35 — Revenue Target Achievement % (KPI measure)
```dax
Revenue Target Achievement % =
VAR MonthlyTarget = 13000000
RETURN
DIVIDE([Total Revenue], MonthlyTarget, 0)
```
Set `MonthlyTarget` to `[Total Revenue] / 36` for a dynamic average-based
target, or hardcode your business target. Used as the **Goal** value in KPI visuals.

---

## PART 6 — DASHBOARD DESIGN: 4 PAGES

---

### PAGE 1 — Executive KPI Summary

**Purpose:** Give a C-suite user the complete business picture in 10 seconds.

**Layout (top to bottom):**

```
┌────────────────────────────────────────────────────────────┐
│  HEADER: "Retail & E-Commerce — Executive Dashboard"       │
│  [Year Slicer]  [Category Slicer]  [Channel Slicer]       │
├──────────┬──────────┬──────────┬──────────┬───────────────┤
│  Total   │  Gross   │ Profit   │ Total    │   Return       │
│ Revenue  │  Profit  │ Margin % │ Orders   │   Rate %       │
│  KPI     │  KPI     │  KPI     │  KPI     │   KPI          │
├──────────┴──────────┴──────────┴──────────┴───────────────┤
│  Monthly Revenue Bar Chart + MoM Growth % Line (combo)    │
│  X-axis: Year-Month  |  Bar: Total Revenue                │
│  Line: MoM Growth %  |  Dual Y-axis                       │
├─────────────────────────┬──────────────────────────────────┤
│  Revenue by Category    │  Revenue by Sales Channel       │
│  Horizontal Bar Chart   │  Donut Chart                    │
│  Sorted descending      │  with % labels                  │
├─────────────────────────┴──────────────────────────────────┤
│  Annual Revenue vs SPLY — Clustered Bar (2022/2023/2024)  │
│  With YoY Growth % data labels                            │
└────────────────────────────────────────────────────────────┘
```

**KPI Visual setup (for each card):**
- Visual: **Card** or **KPI**
- For KPI visual: set Value = measure, Target = Revenue Target Achievement %
- Enable conditional formatting: green if > target, red if below

**Dynamic Title DAX (add to each page title as a text box measure):**
```dax
Page Title =
"Executive Summary — " &
SELECTEDVALUE(Date_Table[Year], "All Years") &
" | " &
SELECTEDVALUE(Products[category], "All Categories")
```

**Conditional formatting on Revenue KPI card:**
- Background color rule: if MoM Growth % > 0 → green (#27AE60), else red (#E74C3C)

---

### PAGE 2 — Sales Deep-Dive

**Purpose:** Let an analyst drill into exactly where revenue comes from.

**Layout:**

```
┌────────────────────────────────────────────────────────────┐
│  HEADER: "Sales Deep-Dive"                                 │
│  [Date Range Slicer]  [State Slicer]  [Status Slicer]     │
├──────────┬──────────┬──────────┬──────────────────────────┤
│  Rolling │  Rolling │  YoY     │  Revenue YTD             │
│  3M Rev  │  12M Rev │ Growth % │  vs Target               │
├──────────┴──────────┴──────────┴──────────────────────────┤
│  Daily Revenue Line Chart with Rolling 30D average        │
│  X: order_date  |  Line 1: daily  |  Line 2: rolling avg  │
├─────────────────────────┬──────────────────────────────────┤
│  Revenue by State       │  AOV Trend by Channel (line)    │
│  Filled Map Visual      │  X: Year-Month                  │
│  Color = total_revenue  │  Lines: one per channel         │
│  Tooltip: orders, AOV   │                                 │
├─────────────────────────┴──────────────────────────────────┤
│  Revenue by Day of Week — Heatmap or Column Chart          │
│  Sorted Mon-Sun  |  Color intensity = revenue             │
└────────────────────────────────────────────────────────────┘
```

**Drill-through setup:**
- Right-click on any Category bar → Drill-through → "Product Detail" page
- Product Detail page shows: top products table, margin bar chart, return rate

**Tooltip page for Map visual:**
Create a hidden page (right-click tab → Hide Page) with:
- State name, total revenue, order count, unique customers, AOV
- Set as tooltip on the map visual

---

### PAGE 3 — Customer Intelligence

**Purpose:** Understand who the customers are and how to retain them.

**Layout:**

```
┌────────────────────────────────────────────────────────────┐
│  HEADER: "Customer Intelligence"                           │
│  [Loyalty Tier Slicer]  [RFM Segment Slicer]              │
├──────────┬──────────┬──────────┬──────────────────────────┤
│  Total   │  Active  │  Avg CLV │  Churn Risk Count        │
│ Customers│Customers │          │  (days since order > 90) │
├──────────┴──────────┴──────────┴──────────────────────────┤
│  RFM Segment Distribution — Treemap or Stacked Bar         │
│  Size/height = customer count | Color = avg revenue       │
├─────────────────────────┬──────────────────────────────────┤
│  New vs Returning       │  Revenue by Loyalty Tier        │
│  Customers Monthly      │  Clustered Bar                  │
│  100% Stacked Area      │  With revenue per customer line │
│  Green=new, Blue=return │                                 │
├─────────────────────────┴──────────────────────────────────┤
│  Cohort Retention Heatmap (from cohort_retention.csv)      │
│  Matrix visual: rows=cohort month, cols=month index 0-12  │
│  Values: retention % | Background color: white→green scale│
└────────────────────────────────────────────────────────────┘
```

**Cohort Heatmap in Power BI:**
1. Load `cohort_retention.csv` (already in data/cleaned/)
2. Use a **Matrix** visual
3. Rows: `cohort_month` | Columns: month index columns (0 through 12)
4. Values: retention values
5. **Format** → **Cell elements** → enable Background color
6. Set color scale: Min = white, Max = dark green

**Bookmark setup:**
- Create Bookmark A: RFM view (treemap visible, cohort hidden)
- Create Bookmark B: Cohort view (heatmap visible, treemap hidden)
- Add two buttons at top: "RFM View" / "Cohort View"
- Assign bookmarks to buttons for a toggle effect

---

### PAGE 4 — Product & Returns Analysis

**Purpose:** Understand product performance, margin, and return health.

**Layout:**

```
┌────────────────────────────────────────────────────────────┐
│  HEADER: "Product & Returns Analysis"                      │
│  [Category Slicer]  [Brand Slicer]  [ABC Class Slicer]    │
├──────────┬──────────┬──────────┬──────────────────────────┤
│  Units   │  Return  │  Total   │  Avg Refund              │
│  Sold    │  Rate %  │  Refunds │  per Return              │
├──────────┴──────────┴──────────┴──────────────────────────┤
│  Top 20 Products Table (sortable)                          │
│  Cols: Product | Category | Revenue | Units | Margin% | ABC│
│  Conditional format: Margin % bar in green/red            │
│  Enable drill-through on product row                      │
├─────────────────────────┬──────────────────────────────────┤
│  Margin % by Category   │  Return Rate by Category        │
│  Bar chart + avg line   │  Bar chart + avg line           │
│  Sorted descending      │  Red if > avg, green if below   │
├─────────────────────────┴──────────────────────────────────┤
│  What-If: Discount Impact Scenario                         │
│  Slicer: Discount Adjustment % (-20 to +20)               │
│  Card: What-If Revenue Impact (M32)                       │
│  Card: Adjusted Revenue = [Total Revenue] + [M32]         │
│  Line chart: current vs what-if revenue by month          │
└────────────────────────────────────────────────────────────┘
```

**Conditional formatting on Products table:**
- Margin % column: Data bar, green = high margin, red = low
- ABC Class column: background color — A=green, B=yellow, C=red
  - Rules: if value contains "A" → #27AE60, "B" → #F39C12, "C" → #E74C3C

---

## PART 7 — FINAL POLISH CHECKLIST

### Slicers (apply to all pages)
- [ ] Year slicer (2022 / 2023 / 2024) — Tile style, multi-select
- [ ] Date range slicer — Between style
- [ ] Category slicer — Dropdown, multi-select
- [ ] Channel slicer — Dropdown
- [ ] Status filter — Tile style (Completed / Shipped / All)

### Visual formatting standards
- [ ] All revenue KPI cards: format numbers as `$#,##0.0,,\M` (millions)
- [ ] All percentage measures: format as `0.0%`
- [ ] Font: Segoe UI throughout
- [ ] Background: white (#FFFFFF) or very light grey (#F8F9FA)
- [ ] Accent colour: #2C3E50 (headers), #3498DB (primary), #27AE60 (positive), #E74C3C (negative)
- [ ] Remove gridlines from all charts
- [ ] Enable data labels on bar charts (top only, not inside)

### Interactivity
- [ ] Edit interactions: ensure category filter filters products table
- [ ] Add "Reset Filters" button on each page (bookmark to default state)
- [ ] Enable cross-highlight between all visuals on a page
- [ ] Add page navigation buttons in top-right corner on all pages

### Performance tips
- [ ] Disable auto date/time: File → Options → Data Load → uncheck "Auto date/time"
- [ ] Hide unused columns from report view (right-click → Hide)
- [ ] Summarize numeric columns correctly (Avg, Sum, Count)
- [ ] Set "Don't summarize" on ID columns

---

## PART 8 — PUBLISHING (optional)

1. **File → Publish → Power BI Service**
2. Choose your workspace
3. In Power BI Service: **Schedule Refresh** to keep data live
4. Share the dashboard link for your portfolio

---

## FILES REFERENCE

```
data/cleaned/          <- Load these as tables
  customers_clean.csv
  products_clean.csv
  orders_clean.csv
  order_items_clean.csv
  returns_clean.csv
  rfm_segments.csv
  cohort_retention.csv

sql/results/           <- Load selected query results
  q07_category_rank.csv
  q10_churn_flagging.csv
  q15_order_frequency_distribution.csv
  q17_discount_impact.csv
  q22_geographic_revenue_by_state.csv

powerbi/
  POWER_BI_GUIDE.md    <- This file
  dax_measures.dax     <- All 35 measures, copy-paste ready
```
