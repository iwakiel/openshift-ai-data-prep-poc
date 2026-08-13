# Sprint 1 — Showcase

This page is designed to be opened during the sprint review call. It covers what was built, the architecture, the data strategy, and what runs today.

Repository: [github.com/iwakiel/openshift-ai-data-prep-poc](https://github.com/iwakiel/openshift-ai-data-prep-poc)

---

## What was delivered

| # | Deliverable | Status | Key artefact |
|---|---|---|---|
| 1 | Five-phase data prep pipeline design | Done | `src/pipeline/` |
| 2 | KFP v2 component implementation (all 5 phases) | Done | `src/pipeline/components.py` |
| 3 | Synthetic retail banking data generators | Done | `src/data_generation/` |
| 4 | MinIO S3 client utilities | Done | `src/ingestion/minio_client.py` |
| 5 | Great Expectations validation suites | Done | `src/validation/expectation_suites.py` |
| 6 | Dockerfile for pipeline component image | Done | `Dockerfile` |
| 7 | Python package setup (installable) | Done | `pyproject.toml` |
| 8 | RHOAI environment verification script | Done | `scripts/verify_rhoai_env.sh` |
| 9 | Open dataset mapping to retail use cases | Done | `docs/data_strategy.md` |
| 10 | Schema questionnaire sent to data scientist | Done | 15 questions, awaiting response |

---

## Pipeline architecture

```mermaid
flowchart LR
    A1[Core banking tables] --> ING
    A2[Open datasets\nKaggle / UCI] --> ING
    A3[Synthetic data\nFaker + CTGAN] --> ING

    subgraph RHOAI [Red Hat OpenShift AI]
        ING[Phase 1\nIngestion\nMinIO S3]
        EDA[Phase 2\nEDA\nydata-profiling]
        CLN[Phase 3\nCleaning\npandas]
        VAL{Phase 4\nValidation\nGreat Expectations}
        FE[Phase 5\nFeatures\nscikit-learn]
        KFP[KFP v2\nOrchestrator]
        MLF[MLflow\nTracking]
    end

    ING --> EDA --> CLN --> VAL
    VAL -->|pass| FE
    VAL -->|fail| HALT([Pipeline halt])
    FE --> F1[Fraud features]
    FE --> F2[Credit risk features]
    FE --> F3[Churn features]

    KFP -.->|triggers| ING & CLN & VAL & FE
    MLF -.->|logs| EDA & VAL & FE
```

---

## Retail banking use cases in scope

```mermaid
flowchart TD
    ULB["ULB Credit Card Fraud\n284K transactions\n0.17% fraud rate\nPCA-anonymised features"] --> FRAUD["Fraud and AML Detection\nBinary classifier\nClass ratio 1:585"]
    HC["Home Credit Default Risk\n300K+ applications\n7 relational tables\n8% default rate"] --> CREDIT["Credit Risk Scoring\nDefault probability\nMulti-table join required"]
    BM["Bank Marketing UCI\n41K contacts\nMacroeconomic features\n11% positive class"] --> CHURN["Customer Churn Prediction\nChurn probability\nObservation window model"]

    FRAUD --> PIPE["Data Preparation Pipeline"]
    CREDIT --> PIPE
    CHURN --> PIPE

    PIPE --> OUT["poc-features/\nML-ready Parquet\nVersioned by run_id"]
```

---

## KFP pipeline component chain

Five components execute in sequence inside a Kubeflow Pipelines v2 run. Each reads from and writes to MinIO S3. The validation component raises a `RuntimeError` on any expectation failure — the pipeline halts rather than propagating bad data.

```mermaid
flowchart LR
    IMG["Docker image\nretail-data-prep:latest"] -.->|base image| C1 & C2 & C3 & C4 & C5

    C1["ingest_retail_data\n500K customers\n2M transactions"]
    C2["profile_dataset\nHTML report\n50K sample"]
    C3["clean_retail_data\nDedup, clip\nFeature derivation"]
    C4{"validate_retail_data\nGreat Expectations\nData contracts"}
    C5["build_retail_features\nJoin + aggregates\nuse_case Parquet"]

    C1 --> C2 --> C3 --> C4
    C4 -->|pass| C5
    C4 -->|fail| ERR([Halt])
    C5 --> OUT[(poc-features/)]
```

---

## Retail banking data model

The synthetic data generators produce four linked tables. The feature engineering component joins customers with aggregated transaction metrics.

```mermaid
erDiagram
    CUSTOMER {
        string customer_id PK
        int    age
        string gender
        string governorate
        string customer_segment
        float  annual_income
        int    credit_score
        int    months_with_bank
        int    num_products
        int    churn_flag
    }
    TRANSACTION {
        string transaction_id PK
        string customer_id FK
        float  amount
        string channel
        string merchant_category
        int    transaction_hour
        bool   is_international
        int    fraud_flag
    }
    LOAN {
        string loan_id PK
        string customer_id FK
        string loan_type
        float  principal_amount
        string delinquency_stage
    }
    ACCOUNT {
        string account_id PK
        string customer_id FK
        string account_type
        float  balance
    }
    CUSTOMER ||--o{ TRANSACTION : makes
    CUSTOMER ||--o{ LOAN : holds
    CUSTOMER ||--o{ ACCOUNT : owns
```

---

## S3 bucket layout

```
MinIO
├── poc-raw/
│   ├── customers/run_id=001/customers.parquet      (500K rows)
│   └── transactions/run_id=001/transactions.parquet (2M rows)
│
├── poc-processed/
│   ├── customers_clean/run_id=001/customers_clean.parquet
│   └── transactions_clean/run_id=001/transactions_clean.parquet
│
├── poc-features/
│   ├── fraud/run_id=001/features.parquet
│   ├── credit_risk/run_id=001/features.parquet
│   └── churn/run_id=001/features.parquet
│
└── poc-reports/
    ├── eda/run_id=001/customers_profile.html
    └── ge/run_id=001/retail_banking.customers.v1.json
```

---

## What runs locally today

No OpenShift cluster needed. Three commands:

```bash
# 1. Install the package
pip install -e ".[pipeline]"

# 2. Generate 500K synthetic retail banking customers
python -m src.data_generation.customers --local-only --records 500000

# 3. Generate 2M linked transactions
python -m src.data_generation.transactions \
    --customers-path /tmp/customers.parquet \
    --local-only \
    --records 2000000
```

---

## What requires the cluster

| Step | What is needed | Action |
|---|---|---|
| Build pipeline image | Docker + OpenShift image registry | `make build-image push-image` |
| Submit KFP run | DSPA provisioned in namespace | `make compile-pipeline` then upload YAML in RHOAI dashboard |
| MLflow tracking | MLflow server deployed | Platform team deployment |

---

## Sprint 2 objectives

| Objective | Description |
|---|---|
| Unblock environment | Run the 7-step verification script, resolve DSPA and MinIO blockers with platform team |
| Schema alignment | Receive data scientist response, update generator configs with real column names and class rates |
| First pipeline run | Ingestion to MinIO, cleaning, GE validation suite passing on RHOAI cluster |
