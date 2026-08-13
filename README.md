# OpenShift AI Retail retail banking data Preparation POC

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

End-to-end data preparation pipeline for retail retail banking ML use cases on Red Hat OpenShift AI (RHOAI). This repository covers Sprint 1 of the POC: architecture design, data sourcing strategy, synthetic data generation, and environment verification.

Model training is out of scope for this phase. The deliverable is ML-ready feature datasets, not models.

---

## Scope

This POC targets the retail banking division. Three ML use cases are in scope:

| Use case | ML task | Target class | Benchmark dataset |
|---|---|---|---|
| Fraud and AML detection | Binary classification | ~1.2% fraud rate | ULB Credit Card Fraud (Kaggle) |
| Credit risk scoring | Default probability | ~8% default rate | Home Credit Default Risk (Kaggle) |
| Customer churn prediction | Churn probability | ~18% churn rate | Bank Marketing UCI |

Customer segmentation (unsupervised) is a fourth use case planned for Sprint 3.

---

## Architecture

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

The pipeline runs on Kubeflow Pipelines v2 (DSPA) with MLflow for experiment tracking. Components are containerised — see the project [Dockerfile](Dockerfile) and [Makefile](Makefile).

Full architecture with bucket layout, ER model, and design decisions: [docs/architecture.md](docs/architecture.md)

Sprint review showcase (all diagrams on one page): [docs/sprint_review.md](docs/sprint_review.md)

---

## Repository structure

```
openshift-ai-data-prep-poc/
|
|-- sprint/
| |-- sprint_01_goals.md Current sprint goals and status
| |-- sprint_02_preview.md Next sprint objectives
| `-- definition_of_done.md DoD for all pipeline work
|
|-- docs/
| |-- architecture.md Pipeline design and platform components
| |-- data_strategy.md Dataset sourcing and synthetic data approach
| `-- environment_checklist.md RHOAI setup verification (7 steps)
|
|-- src/
| |-- config.py Central configuration (env vars)
| |-- data_generation/
| | |-- customers.py Synthetic retail customer generator
| | `-- transactions.py Synthetic transaction generator
| |-- ingestion/
| | `-- minio_client.py MinIO S3 utilities
| |-- pipeline/
| | |-- components.py KFP v2 component definitions
| | `-- banking_pipeline.py Pipeline definition and compiler
| `-- validation/
| `-- expectation_suites.py Great Expectations suites
|
|-- scripts/
| `-- verify_rhoai_env.sh One-shot RHOAI environment checker
|
|-- Dockerfile Pipeline component image
|-- Makefile Common operations
|-- pyproject.toml Package definition
`-- .env.example Environment variable template
```

---

## What is and is not operational

**Works as-is (local):**
- Synthetic data generators (`src/data_generation/`)
- MinIO client utilities (`src/ingestion/minio_client.py`)
- Great Expectations suites (`src/validation/expectation_suites.py`)
- Environment verification script (`scripts/verify_rhoai_env.sh`)

**Requires setup before use:**
- KFP pipeline components: need the Docker image built and pushed first (`make build-image push-image`). The components import from the `src` package, which must be baked into the image.
- Pipeline compilation and submission: requires a running DSPA in your RHOAI namespace.
- MLflow: requires a running MLflow server in the namespace.

See [docs/environment_checklist.md](docs/environment_checklist.md) for the full verification procedure.

---

## Getting started

### Prerequisites

- Python 3.9+
- Red Hat OpenShift AI 2.x cluster
- MinIO or ODF (S3-compatible object storage) provisioned
- Kubeflow Pipelines v2 (DSPA) in your namespace

### Install

```bash
git clone https://github.com/iwakiel/openshift-ai-data-prep-poc.git
cd openshift-ai-data-prep-poc
pip install -e ".[pipeline]"
```

### Configure

```bash
cp .env.example .env
# Fill in your MinIO endpoint, credentials, and KFP endpoint
source .env
```

### Verify the RHOAI environment

```bash
make verify-env NAMESPACE=<your-namespace>
```

### Build the pipeline component image

```bash
make build-image push-image NAMESPACE=<your-namespace>
```

### Generate synthetic retail retail banking data

```bash
make generate-data
```

### Compile and submit the pipeline

```bash
# Compile to YAML only (no cluster needed)
make compile-pipeline

# Compile and submit
python -m src.pipeline.banking_pipeline \
 --use-case churn \
 --n-customers 500000 \
 --kfp-endpoint https://ds-pipeline-dspa.<namespace>.svc:8443
```

---

## Open datasets

| Dataset | Use case | Source |
|---|---|---|
| ULB Credit Card Fraud Detection | Fraud and AML | [Kaggle](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) |
| Home Credit Default Risk | Credit risk | [Kaggle](https://www.kaggle.com/competitions/home-credit-default-risk) |
| Bank Marketing | Churn proxy | [UCI ML Repository](https://archive.ics.uci.edu/dataset/222/bank+marketing) |
| Default of Credit Card Clients | Credit risk baseline | [UCI ML Repository](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) |

---

## Tech stack

| Layer | Technology |
|---|---|
| ML platform | Red Hat OpenShift AI 2.x |
| Pipeline orchestration | Kubeflow Pipelines v2 (KFP SDK 2.x) |
| Object storage | MinIO / OpenShift Data Foundation (S3) |
| Data processing | pandas, PySpark, scikit-learn |
| Data quality | Great Expectations 0.18.x |
| Experiment tracking | MLflow |
| Synthetic data | Faker (ar_EG locale), SDV, CTGAN |

---

## Sprint status

Sprint 1 (current): architecture designed, data strategy defined, environment checklist ready, data scientist schema request sent.

Sprint 2 (planned): environment verification, synthetic data generation, first end-to-end pipeline run.

[sprint/sprint_01_goals.md](sprint/sprint_01_goals.md)

---

## License

[MIT](LICENSE)
