# Sprint 2 Build & Validate

**Sprint Goal:** Resolve environment blockers, generate the first synthetic data batch, and deliver a functional end-to-end data preparation pipeline run on RHOAI.

**Status:** Planned

---

## Objectives

### 1. Environment Unblocking (Priority: High)
- Run the 7-step RHOAI verification checklist via privileged access session
- Raise platform team ticket to provision DSPA pipeline server (if not present)
- Confirm MinIO S3 connectivity from workbench pods
- Confirm internal PyPI mirror URL for required packages

### 2. Synthetic Data Generation (Priority: High)
- Receive schema questionnaire response from retail data scientist
- Update generator configs with: column names, value ranges, class imbalance rates
- Generate 500K customer records + 2M transaction events
- Upload to MinIO `poc-raw/` bucket with versioned Parquet partitions
- Validate output against schema expectations

### 3. First End-to-End Pipeline Run (Priority: High)
- Stand up ingestion component: MinIO upload `poc-raw/`
- Run EDA notebook on sample (10K records) and save profile report
- Execute cleaning pipeline component (nulls, outliers, encoding)
- Run Great Expectations validation suite must achieve 100% pass rate
- Output ML-ready Parquet to `poc-features/` bucket

### 4. MLflow Integration (Priority: Medium)
- Connect workbench to MLflow tracking server
- Log data profile metrics as MLflow run parameters
- Log GE validation results as MLflow run artifacts

---

## Definition of Done

See [`definition_of_done.md`](definition_of_done.md).

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Schema info not received from data scientist | Medium | High | Use best-guess schema from open datasets as fallback |
| DSPA provisioning delayed by platform team | Medium | High | Use KFP local runner for component testing while waiting |
| PyPI blocked, packages unavailable | Low | Medium | Pre-build custom workbench image with required packages |
