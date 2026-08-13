# Data Directory

This directory is excluded from version control via `.gitignore`.

The `samples/` subdirectory contains 20-row CSV files for documentation only.
The `raw/` subdirectory contains generated Parquet files — these are not committed.

---

## How to generate the data

```bash
pip install -e ".[pipeline]"

# Generate customers (writes to /tmp by default without MinIO)
python -m src.data_generation.customers --local-only --records 100000

# Generate transactions linked to those customers
python -m src.data_generation.transactions \
    --customers-path /tmp/customers.parquet \
    --local-only \
    --records 500000
```

Or with MinIO available:

```bash
make generate-data
```

---

## Generation output (Sprint 1 run)

| Dataset | Rows | Columns | Parquet size |
|---|---|---|---|
| customers | 100,000 | 17 | 8.2 MB |
| transactions | 500,000 | 11 | 22.3 MB |

### Statistical properties

| Property | Value | Target |
|---|---|---|
| Churn rate | 17.9% | 18% |
| Fraud rate | 1.20% | 1.2% |
| Active customers | 80.0% | 80% |
| Loan holders | 38.0% | 38% |
| Avg credit score | 627 | 620 |
| Median income | 29,796 EGP | — |
| Income range | 1,500 – 763,470 EGP | — |

### Governorate distribution

| Governorate | Count | Share |
|---|---|---|
| Cairo | 30,123 | 30% |
| Giza | 17,964 | 18% |
| Alexandria | 14,105 | 14% |
| Qalyubia | 8,022 | 8% |
| Sharqia | 5,922 | 6% |
| Dakahlia | 5,972 | 6% |
| Other | 18,892 | 18% |

### Transaction channel split

| Channel | Count | Share |
|---|---|---|
| POS | 160,067 | 32% |
| ATM | 150,325 | 30% |
| Online | 124,845 | 25% |
| Mobile | 49,770 | 10% |
| Branch | 14,993 | 3% |

---

## Locale and format notes

- Names generated using Faker `ar_AA` locale (Arabic script)
- National IDs follow the Egyptian 14-digit format: `[century][YY][MM][DD][governorate][seq]`
- Phone numbers use Egyptian mobile prefixes: +20 010, 011, 012, 015
- Income values calibrated to Egyptian pound ranges (EGP)
- All amounts in EGP unless `currency` column indicates otherwise (93% EGP)

---

## Why not commit the Parquet files?

Git is not a data store. Binary files inflate repository history permanently and cannot be
cleanly removed once committed. The code that generates the data is version-controlled here.
The data itself lives in MinIO (when the cluster environment is available) or locally on the
developer's machine. For large-scale data versioning, DVC (Data Version Control) is the
standard tool — this is a planned addition for a later sprint.
