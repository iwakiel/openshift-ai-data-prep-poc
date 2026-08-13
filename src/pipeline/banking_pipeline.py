"""
Retail Banking Data Preparation Pipeline — KFP v2 definition.

Compiles and optionally submits the five-phase data preparation pipeline
to a Kubeflow Pipelines server running on Red Hat OpenShift AI.
"""
import logging
import os
from pathlib import Path

from kfp import compiler, dsl
from kfp.client import Client

from src.config import config
from src.pipeline.components import (
    build_features,
    clean_and_transform,
    ingest_data,
    run_eda,
    validate_quality,
)

logger = logging.getLogger(__name__)


@dsl.pipeline(
    name="retail-banking-data-prep",
    description=(
        "End-to-end data preparation pipeline for retail banking ML use cases. "
        "Covers: ingestion → EDA → cleaning → quality validation → feature engineering."
    ),
)
def banking_data_prep_pipeline(
    minio_endpoint: str = config.storage.endpoint_url,
    raw_bucket: str = config.storage.raw_bucket,
    processed_bucket: str = config.storage.processed_bucket,
    features_bucket: str = config.storage.features_bucket,
    reports_bucket: str = config.storage.reports_bucket,
    use_case: str = "churn",
    n_customers: int = 500_000,
    suite_name: str = "retail_banking_suite_v1",
    run_id: str = "run_001",
) -> None:
    """
    Five-phase data preparation pipeline for retail banking ML.

    Args:
        minio_endpoint: MinIO S3 endpoint URL.
        raw_bucket: Bucket for raw ingested data.
        processed_bucket: Bucket for cleaned/processed data.
        features_bucket: Bucket for ML-ready feature datasets.
        reports_bucket: Bucket for EDA profiles and GE validation reports.
        use_case: Target ML use case — 'fraud', 'credit_risk', or 'churn'.
        n_customers: Number of synthetic customer records to generate.
        suite_name: Great Expectations suite name to use for validation.
        run_id: Unique identifier for this pipeline run.
    """
    # Phase 1: Ingest synthetic data into MinIO
    ingest_task = ingest_data(
        minio_endpoint=minio_endpoint,
        raw_bucket=raw_bucket,
        use_case=use_case,
        n_customers=n_customers,
    )
    ingest_task.set_display_name("1 · Ingest Data")
    ingest_task.set_caching_options(False)

    # Phase 2: EDA and profiling
    eda_task = run_eda(
        input_dataset=ingest_task.outputs["output_dataset"],
        reports_bucket=reports_bucket,
        run_id=run_id,
    )
    eda_task.set_display_name("2 · EDA & Profiling")

    # Phase 3: Cleaning and transformation (runs in parallel with EDA)
    clean_task = clean_and_transform(
        input_dataset=ingest_task.outputs["output_dataset"],
        processed_bucket=processed_bucket,
        run_id=run_id,
    )
    clean_task.set_display_name("3 · Clean & Transform")
    clean_task.after(eda_task)  # ensure EDA completes before cleaning

    # Phase 4: Quality validation — pipeline halts if expectations fail
    validate_task = validate_quality(
        input_dataset=clean_task.outputs["output_dataset"],
        reports_bucket=reports_bucket,
        suite_name=suite_name,
        run_id=run_id,
    )
    validate_task.set_display_name("4 · Quality Validation")

    # Phase 5: Feature engineering for the target use case
    feature_task = build_features(
        input_dataset=clean_task.outputs["output_dataset"],
        features_bucket=features_bucket,
        use_case=use_case,
        run_id=run_id,
    )
    feature_task.set_display_name("5 · Build Features")
    feature_task.after(validate_task)


def compile_pipeline(output_path: str = "banking_pipeline.yaml") -> str:
    """
    Compile the pipeline to a YAML file for upload to RHOAI.

    Args:
        output_path: Destination path for the compiled YAML.

    Returns:
        Absolute path to the compiled YAML file.
    """
    compiler.Compiler().compile(banking_data_prep_pipeline, output_path)
    logger.info(f"Pipeline compiled → {output_path}")
    return str(Path(output_path).resolve())


def compile_and_run(
    kfp_endpoint: str = "",
    use_case: str = "churn",
    n_customers: int = 500_000,
    run_id: str = "run_001",
    compile_only: bool = False,
) -> None:
    """
    Compile the pipeline and optionally submit a run to KFP.

    Args:
        kfp_endpoint: KFP API endpoint. If empty, compile only.
        use_case: ML use case to run — 'fraud', 'credit_risk', or 'churn'.
        n_customers: Number of synthetic records to generate.
        run_id: Unique run identifier.
        compile_only: If True, compile YAML but do not submit.
    """
    yaml_path = compile_pipeline()

    if compile_only or not kfp_endpoint:
        logger.info("Compile-only mode. Pipeline YAML ready for manual upload.")
        return

    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    if not os.path.exists(token_path):
        raise EnvironmentError(
            "Service account token not found. "
            "Ensure this script runs inside an OpenShift workbench pod."
        )

    with open(token_path) as f:
        token = f.read().strip()

    client = Client(host=kfp_endpoint, existing_token=token)

    run = client.create_run_from_pipeline_func(
        banking_data_prep_pipeline,
        arguments={
            "use_case":    use_case,
            "n_customers": n_customers,
            "run_id":      run_id,
            "minio_endpoint":   config.storage.endpoint_url,
            "raw_bucket":       config.storage.raw_bucket,
            "processed_bucket": config.storage.processed_bucket,
            "features_bucket":  config.storage.features_bucket,
            "reports_bucket":   config.storage.reports_bucket,
        },
        experiment_name=config.mlflow.experiment_name,
        run_name=f"data-prep-{use_case}-{run_id}",
    )

    logger.info(f"Pipeline run submitted: {run.run_id}")
    logger.info(f"View at: {kfp_endpoint}/#/runs/details/{run.run_id}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compile and run the data prep pipeline")
    parser.add_argument("--use-case",      default="churn",   choices=["fraud", "credit_risk", "churn"])
    parser.add_argument("--n-customers",   type=int,          default=500_000)
    parser.add_argument("--run-id",        default="run_001")
    parser.add_argument("--kfp-endpoint",  default="")
    parser.add_argument("--compile-only",  action="store_true")
    args = parser.parse_args()

    compile_and_run(
        kfp_endpoint=args.kfp_endpoint,
        use_case=args.use_case,
        n_customers=args.n_customers,
        run_id=args.run_id,
        compile_only=args.compile_only,
    )
