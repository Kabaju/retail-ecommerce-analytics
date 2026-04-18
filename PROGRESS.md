# Retail & E-Commerce Analytics Project — Progress Log

**Last updated:** 2026-04-18
**Current phase:** Phase 4 COMPLETE — awaiting confirmation to begin Phase 5

---

## COMPLETED

### Phase 1 — Data Generation & Raw Ingestion

- [x] Project folder structure created
      data/raw, data/cleaned, sql, notebooks, powerbi, reports, scripts
- [x] scripts/generate_data.py written
      Full 5-table generation with 25 intentional data-quality issues embedded
- [x] All 5 raw CSVs saved to data/raw/

| File            | Rows    | Notes                        |
|-----------------|---------|------------------------------|
| customers.csv   | 10,050  | includes ~50 duplicate rows  |
| products.csv    | 510     | includes ~10 duplicate rows  |
| orders.csv      | 100,200 | includes ~200 duplicate rows |
| order_items.csv | 300,300 | includes ~300 duplicate rows |
| returns.csv     | 8,080   | includes ~80 duplicate rows  |

---

## IN PROGRESS

Awaiting user confirmation to begin Phase 5 (GitHub Repository)

---

## REMAINING

### Phase 2 — Python Cleaning & EDA  [COMPLETE]
- [x] Load all CSVs with pandas
- [x] Full data-quality audit
- [x] Null handling (imputation vs. drop, with justification)
- [x] Deduplication
- [x] Dtype enforcement + date normalization
- [x] Outlier detection (IQR + Z-score)
- [x] String normalization
- [x] Referential integrity checks across tables
- [x] Data quality report -> reports/data_quality_report.txt
- [x] EDA: 16 publication-quality plots (sales trends, RFM, cohort, returns)
- [x] Export cleaned CSVs + EDA report -> reports/eda_summary_report.txt

### Phase 3 — SQL Database & Advanced Analytics  [COMPLETE]
- [x] Normalized SQLite DB (sql/retail.db) -- 5 tables, 7 indexes, FK schema
- [x] 22 advanced SQL queries (CTEs, LAG/LEAD/RANK/DENSE_RANK, rolling windows,
      CLV, churn flagging, cohort revenue, product affinity, discount impact)
- [x] 22 query result CSVs exported to sql/results/ for Power BI
- [x] Schema saved to sql/schema.sql, all queries to sql/queries.sql

### Phase 4 — Power BI Dashboard  [COMPLETE]
- [x] Complete step-by-step data loading guide (11 tables)
- [x] Star schema data model with 7 relationships documented
- [x] DAX Date_Table creation script
- [x] 35 DAX measures across 7 sections (Revenue, Growth, Rolling,
      Customer, Returns, Advanced) -- saved to powerbi/dax_measures.dax
- [x] 4-page dashboard design specs with layouts, visuals, slicers,
      conditional formatting, bookmarks, drill-throughs, tooltip pages
- [x] What-If discount scenario parameter documented
- [x] Dynamic ABC classification calculated column
- [x] Full guide saved to powerbi/POWER_BI_GUIDE.md

### Phase 5 — GitHub Repository
- [ ] Professional README.md
- [ ] .gitignore + requirements.txt
- [ ] Git init, conventional commits, push

---

## RESUME INSTRUCTIONS

To pick up in a new session:

1. Working directory: C:\Users\DELL\Retail & E-Commerce Project
2. Phase 1 is complete — all raw CSVs are in data/raw/
3. Next step: Phase 2 — script will be at scripts/clean_and_eda.py
4. Phase 3 script: scripts/build_database.py + sql/queries.sql
5. Tech stack: Python 3.12, pandas, faker, numpy, matplotlib, seaborn, sqlite3

---

## DATA QUALITY ISSUES EMBEDDED (Phase 1)

| #  | Table       | Issue                                              | Approx. affected |
|----|-------------|----------------------------------------------------|------------------|
| 1  | customers   | Inconsistent name casing (UPPER / lower)           | ~10%             |
| 2  | customers   | Duplicate emails across different customer IDs     | ~2%              |
| 3  | customers   | Malformed emails (AT / DOT substitutions)          | ~1.5%            |
| 4  | customers   | NULL phone and date_of_birth                       | ~5% / ~3%        |
| 5  | customers   | Loyalty tier typos (Bronz, Platinium, GOLD)        | ~0.5%            |
| 6  | customers   | Fully duplicate rows                               | 50 rows          |
| 7  | products    | Currency symbol in price field (EUR, GBP strings)  | ~3%              |
| 8  | products    | NULL supplier_id                                   | ~4%              |
| 9  | products    | 100x price outlier (data entry error)              | ~0.5%            |
| 10 | products    | ALL-CAPS product names                             | ~8%              |
| 11 | products    | Fully duplicate rows                               | 10 rows          |
| 12 | orders      | Ship date before order date                        | ~1%              |
| 13 | orders      | Malformed order date (MM-DD-YYYY instead of ISO)   | ~1.5%            |
| 14 | orders      | NULL customer_id (orphaned orders)                 | ~0.5%            |
| 15 | orders      | Outlier shipping cost ($500-$9999)                 | ~0.3%            |
| 16 | orders      | Fully duplicate rows                               | 200 rows         |
| 17 | order_items | Negative quantity values                           | ~0.4%            |
| 18 | order_items | NULL unit_price                                    | ~1%              |
| 19 | order_items | Orphaned product_id (references deleted products)  | ~0.2%            |
| 20 | order_items | Fully duplicate rows                               | 300 rows         |
| 21 | returns     | Malformed return date ("15 Mar 2023" format)       | ~2%              |
| 22 | returns     | Outlier refund amount ($10,000-$99,999)            | ~0.3%            |
| 23 | returns     | NULL return reason                                 | ~6%              |
| 24 | returns     | Orphaned product_id                                | ~1%              |
| 25 | returns     | Fully duplicate rows                               | 80 rows          |
