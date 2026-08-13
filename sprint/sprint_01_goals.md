# Sprint 1 — Design & Validation

**Sprint Goal:** Design and validate the full data preparation approach for the OpenShift AI POC, covering pipeline architecture, data sourcing strategy, and environment readiness across three retail banking use cases.

**Duration:** 2 weeks  
**Role:** MLOps Engineer  
**Status:** 🟡 In Progress

---

## ✅ Completed This Sprint

### 1. Pipeline Architecture Design
**Status:** ✅ Done

Designed the full five-phase data preparation pipeline on Red Hat OpenShift AI:

- **Phase 1 — Ingestion:** Raw data ingested from source systems and benchmark datasets into MinIO S3 (`poc-raw/` bucket), using versioned Parquet partitions.
- **Phase 2 — EDA & Profiling:** Exploratory analysis performed in Jupyter Workbench using `pandas` and `ydata-profiling`. HTML profile reports stored back to S3.
- **Phase 3 — Cleaning & Transformation:** Null handling, outlier clipping, categorical encoding, and feature derivation implemented as reusable, unit-testable Python functions.
- **Phase 4 — Quality Validation:** Great Expectations suite validates business rules, schema integrity, and statistical expectations. Pipeline fails loudly on contract violations.
- **Phase 5 — Feature Output:** ML-ready feature datasets written as Parquet files to `poc-features/` bucket, versioned by use case and run ID.

**Artefacts:**
- Architecture diagram (see [`docs/architecture.md`](../docs/architecture.md))
- KFP pipeline components (`src/pipeline/components.py`)
- Pipeline definition (`src/pipeline/banking_pipeline.py`)

---

### 2. Data Sourcing Strategy
**Status:** ✅ Done

Defined a three-track data strategy for the POC environment:

| Track | Description | Status |
|---|---|---|
| Open benchmark datasets | Public ML datasets mapped to each use case | ✅ Identified & documented |
| Synthetic data generation | 500K records using Faker (ar_EG locale) + CTGAN | ✅ Generator code written |
| Schema alignment | 15 questions sent to retail data scientist for schema/distribution info | 🔄 Awaiting response |

**Open datasets identified:**
- ULB Credit Card Fraud → Fraud detection baseline
- Home Credit Default Risk → Credit risk multi-table pipeline
- Bank Marketing UCI → Customer churn proxy

**Artefacts:**
- Data strategy documentation (`docs/data_strategy.md`)
- Synthetic data generators (`src/data_generation/`)
- Schema questionnaire sent to data scientist

---

### 3. Environment Verification Checklist
**Status:** ✅ Designed, 🔄 Execution Pending

Built a seven-step verification checklist to confirm RHOAI setup readiness via privileged access session:

| # | Check | Tool | Status |
|---|---|---|---|
| 1 | RHOAI operator running and version ≥ 2.x | `oc get csv` | 🔄 Pending |
| 2 | MinIO / ODF storage backend available | `oc get pods -n redhat-ods-applications` | 🔄 Pending |
| 3 | Data Science Pipeline (DSPA) server provisioned | `oc get dspa` | 🔄 Pending |
| 4 | Workbench runtime images available (Python 3.9+) | `oc get imagestreams` | 🔄 Pending |
| 5 | Namespace resource quotas sufficient | `oc get resourcequota` | 🔄 Pending |
| 6 | Network policies allow workbench → S3 connectivity | Direct connectivity test | 🔄 Pending |
| 7 | Python package access (internal PyPI mirror or internet) | `pip install` test | 🔄 Pending |

**Three potential blockers flagged:**
- ❗ DSPA pipeline server may not yet be provisioned in target namespace
- ❗ MinIO S3 connectivity from workbench pods is unconfirmed
- ❗ PyPI package access behind bank network firewall needs platform team sign-off

**Artefacts:**
- Verification script (`scripts/verify_rhoai_env.sh`)

---

### 4. Cloudera ML Evaluation (Parallel Track)
**Status:** ✅ Done

Created Jira user stories for platform capability validation with Cloudera admins, covering:
- Multi-kernel and Python version support
- Spark runtime availability
- Resource profiling and cross-tenant contention
- Audit logging and governance
- Versioning and model registry support

---

## 🔄 In Progress

- Awaiting schema information from retail data scientist (column names, value ranges, class rates for fraud, credit risk, and churn models)
- Environment verification session to be scheduled

---

## 📋 Next Sprint Preview

See [`sprint_02_preview.md`](sprint_02_preview.md) for Sprint 2 objectives.

| Objective | Description |
|---|---|
| 🔧 Unblock environment | Run verification checklist, resolve DSPA and MinIO blockers with platform team |
| 🗄️ Generate synthetic data | Use schema from data scientist to generate 500K-record batch |
| 🚀 First pipeline run | Stand up end-to-end: ingestion → cleaning → GE validation on RHOAI |

---

## 📊 Sprint Metrics

| Metric | Value |
|---|---|
| Story points planned | 21 |
| Story points completed | 13 |
| Blockers identified | 3 |
| Pipeline components written | 5 |
| Open datasets mapped | 3 |
| Schema questions drafted | 15 |
| Documentation pages | 4 |
