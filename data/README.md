# Data Directory

Raw Parquet files (data/raw/) are excluded from version control.
Sample CSVs (data/samples/) are included for documentation only — 20 rows each.

To regenerate the full dataset locally:

```bash
pip install -e ".[pipeline]"
python -m src.data_generation.customers --local-only --records 100000
python -m src.data_generation.transactions \
    --customers-path /tmp/customers.parquet \
    --local-only --records 500000
```

---

## Phase samples

Each file shows what the data looks like at one stage of the pipeline.
The column differences between files illustrate exactly what each phase does.

| File | Phase | Description |
|---|---|---|
| phase1_raw_customers.csv | 1 — Ingestion | 17 columns — raw customer data as generated, nothing modified |
| phase1_raw_transactions.csv | 1 — Ingestion | 11 columns — raw transaction data with fraud flag |
| phase2_eda_profile.csv | 2 — EDA | One row per column: dtype, null count, mean, std, min, max, top values |
| phase3_clean_customers.csv | 3 — Cleaning | 20 columns — same rows as Phase 1 but nulls filled, outliers clipped, 3 new derived columns |
| phase4_validation_result.json | 4 — Validation | Great Expectations result: 9 expectations evaluated, all passed |
| phase5_features_churn.csv | 5 — Features | 24 columns — customer features joined with 8 transaction aggregates, churn_flag as label |
| phase5_features_fraud.csv | 5 — Features | 20 columns — fraud-focused feature set with transaction behaviour signals |

---

## What changes between phases

Phase 1 → Phase 3 (Cleaning adds 3 columns):
- tenure_years: months_with_bank divided by 12
- income_per_product: annual_income_egp divided by num_products
- credit_tier: categorical bucketing of credit_score (very_poor / poor / fair / good / very_good / excellent)

Phase 3 → Phase 5 (Feature engineering adds transaction aggregates):
- txn_count: total number of transactions per customer
- total_spend_egp: sum of all transaction amounts
- avg_txn_egp: average transaction amount
- online_txn_pct: share of transactions on Online channel
- mobile_txn_pct: share of transactions on Mobile channel
- night_txn_pct: share of transactions between midnight and 06:00
- intl_txn_pct: share of international transactions
- unique_channels: number of distinct channels used

---

## Name format

All Arabic names follow the 4-part Egyptian official format:
  first_name  father_first_name  grandfather_first_name  family_name

Example: فاطمة أحمد محمود إبراهيم

No titles or honorifics (no الدكتور, الأستاذ, السيد, etc.).
Names generated using curated lists of common Egyptian first names and family names.

---

## Generation statistics (Sprint 1 run)

| Dataset | Rows | Parquet size |
|---|---|---|
| customers | 100,000 | 8.2 MB |
| transactions | 500,000 | 22.3 MB |

| Metric | Value | Target |
|---|---|---|
| Churn rate | 17.9% | 18% |
| Fraud rate | 1.20% | 1.2% |
| Active customers | 80.0% | 80% |
| Avg credit score | 627 | — |
| Median income | 29,796 EGP | — |
