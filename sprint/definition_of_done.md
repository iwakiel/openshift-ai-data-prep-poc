# Definition of Done

All pipeline components and documentation must meet the following criteria before a story is considered complete.

---

## Code

- [ ] All functions have type hints and docstrings
- [ ] Unit tests written and passing (`pytest`)
- [ ] No hardcoded credentials or endpoints (environment variables only)
- [ ] Code reviewed and merged to `main` via pull request
- [ ] Linting passes (`flake8`, `black`)

## Data Pipeline Components

- [ ] Component runs successfully as a standalone function (local runner)
- [ ] Component runs successfully as a KFP v2 component on RHOAI
- [ ] Input/output types declared with `dsl.Dataset` / `dsl.Artifact`
- [ ] Component logs meaningful messages at INFO level
- [ ] Component fails loudly (exception, non-zero exit) on data contract violation

## Data Quality

- [ ] Great Expectations suite defined for all output datasets
- [ ] All expectations pass on generated/processed data
- [ ] Validation report saved to `poc-reports/` S3 bucket
- [ ] Class imbalance ratio verified against expected rate (±10%)

## Documentation

- [ ] Architecture or design change reflected in `docs/`
- [ ] Sprint goals updated in `sprint/`
- [ ] README updated if new component or dependency added

## MLflow

- [ ] Pipeline run logged to MLflow experiment
- [ ] Data profile metrics captured as run parameters
- [ ] Output dataset path and schema logged as run artifacts
