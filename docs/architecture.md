# Architecture

## Overview

The data preparation POC is structured as a five-phase pipeline running entirely inside Red Hat OpenShift AI (RHOAI). The pipeline is orchestrated by Kubeflow Pipelines v2 (via the Data Science Pipelines Application DSPA), with experiment metadata tracked in MLflow.

---

## Platform Components

```
┌─────────────────────────────────────────────────────────────────┐
│ Red Hat OpenShift AI Platform │
│ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│ │ Jupyter │ │ MinIO / │ │ Data Science │ │
│ │ Workbench │ │ ODF (S3) │ │ Pipeline (DSPA) │ │
│ │ (Notebooks) │ │ Storage │ │ Kubeflow Pipelines │ │
│ └──────────────┘ └──────────────┘ └──────────────────────┘ │
│ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│ │ MLflow │ │ Container │ │ RBAC / Namespace │ │
│ │ Tracking │ │ Registry │ │ Resource Quotas │ │
│ └──────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Data Flow

```mermaid
flowchart TD
 A1[Core retail banking data\nCSV / DB extract] --> ING
 A2[Open Benchmark Datasets\nKaggle / UCI] --> ING
 A3[Synthetic Data\nFaker + SDV/CTGAN] --> ING

 ING[Phase 1\nData Ingestion\nboto3 / MinIO] --> RAW[(poc-raw/\nMinIO S3\nParquet)]

 RAW --> EDA[Phase 2\nEDA & Profiling\nydata-profiling]
 EDA --> REPORT[(poc-reports/\nHTML Profile)]

 RAW --> CLN[Phase 3\nCleaning & Transform\npandas / PySpark]
 CLN --> CLEAN[(poc-processed/\nClean Parquet)]

 CLEAN --> VAL[Phase 4\nQuality Validation\nGreat Expectations]
 VAL -->|Pass| FE[Phase 5\nFeature Engineering\nscikit-learn]
 VAL -->|Fail| HALT[ Pipeline Halt\nAlert + Report]

 FE --> FEAT[(poc-features/\nML-Ready Parquet)]

 FEAT --> M1[Fraud Detection\nModel Training]
 FEAT --> M2[Credit Risk\nModel Training]
 FEAT --> M3[Churn Prediction\nModel Training]

 KFP[KFP v2 Orchestrator] -. triggers .-> ING
 KFP -. triggers .-> CLN
 KFP -. triggers .-> VAL
 KFP -. triggers .-> FE

 MLF[MLflow Tracking] -. logs .-> EDA
 MLF -. logs .-> VAL
 MLF -. logs .-> FE
```

---

## Bucket Structure

```
MinIO
├── poc-raw/
│ ├── customers/
│ │ └── v=1/date=2025-01-01/customers.parquet
│ └── transactions/
│ └── v=1/date=2025-01-01/transactions.parquet
│
├── poc-processed/
│ ├── customers_clean/
│ └── transactions_clean/
│
├── poc-features/
│ ├── fraud/
│ │ └── v=1/features.parquet
│ ├── credit_risk/
│ │ └── v=1/features.parquet
│ └── churn/
│ └── v=1/features.parquet
│
└── poc-reports/
 ├── profiles/
 └── ge_validations/
```

---

## Design Decisions

### Why MinIO for storage?
MinIO is the default S3-compatible object store bundled with RHOAI (via OpenShift Data Foundation). Using S3-compatible APIs means zero code changes if we migrate to AWS S3 or another object store.

### Why Kubeflow Pipelines v2?
RHOAI ships with a managed KFP v2 server via the DSPA operator. KFP v2 provides: strongly-typed component I/O, artifact lineage, pipeline versioning, and scheduled runs all without additional infrastructure.

### Why Great Expectations over custom validation?
GE provides a declarative, version-controlled data contract that integrates with MLflow and produces shareable HTML reports. It separates data quality logic from processing logic, making it easier to maintain as schemas evolve.

### Why Parquet for storage format?
Parquet provides: columnar compression (410× size reduction), schema enforcement, partition pruning for large datasets, and native support in pandas, PySpark, and DuckDB all tools in this pipeline.

---

## Resource Profiles

| Workload | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---|---|---|---|---|
| EDA notebook (light) | 1 | 2 | 4Gi | 8Gi |
| Cleaning pipeline (pandas) | 2 | 4 | 8Gi | 16Gi |
| Feature engineering (PySpark) | 4 | 8 | 16Gi | 32Gi |
| GE validation | 1 | 2 | 2Gi | 4Gi |

---

## KFP Component Chain

The five KFP v2 components execute in the following order. EDA and cleaning run sequentially (cleaning waits for EDA) to let the profile report inform transformation choices before committing.

```mermaid
flowchart LR
    IMG["Docker image\nretail-data-prep:latest\nsrc package installed"] -.->|base| C1 & C2 & C3 & C4 & C5

    C1["ingest_retail_data\n500K customers\n2M transactions\nMinIO upload"]
    C2["profile_dataset\nSample 50K rows\nHTML report\nydata-profiling"]
    C3["clean_retail_data\nDedup on PK\n3-sigma clip\nFeature derivation"]
    C4["validate_retail_data\nExpectation suite\nRaises on failure\nSaves GE JSON"]
    C5["build_retail_features\nJoin customers + txns\nUse-case aggregates\nParquet output"]

    C1 -->|customers_uri\ntransactions_uri| C2
    C1 -->|customers_uri\ntransactions_uri| C3
    C2 -->|after| C3
    C3 -->|output_uri| C4
    C4 -->|result_uri\npass only| C5
    C4 -->|fail| ERR([RuntimeError\npipeline halts])
    C5 --> OUT[(poc-features/\nuse_case=fraud\nuse_case=credit_risk\nuse_case=churn)]
```

---

## Retail Banking Data Model

Schema of the simulated and synthetically-generated tables. Foreign key relationships define the join logic used in the feature engineering component.

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
        bool   has_loan
        bool   has_credit_card
        bool   has_savings_account
        bool   is_active
        int    churn_flag
    }

    ACCOUNT {
        string account_id PK
        string customer_id FK
        string account_type
        float  balance
        string status
    }

    TRANSACTION {
        string transaction_id PK
        string customer_id FK
        float  amount
        string currency
        string channel
        string merchant_category
        int    transaction_hour
        int    transaction_dow
        bool   is_international
        string pos_entry_mode
        int    fraud_flag
    }

    LOAN {
        string loan_id PK
        string customer_id FK
        string loan_type
        float  principal_amount
        int    tenor_months
        float  interest_rate
        string delinquency_stage
    }

    CUSTOMER ||--o{ ACCOUNT : owns
    CUSTOMER ||--o{ TRANSACTION : makes
    CUSTOMER ||--o{ LOAN : holds
    ACCOUNT  ||--o{ TRANSACTION : associated_with
```

