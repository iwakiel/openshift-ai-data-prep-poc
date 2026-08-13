"""
Kubeflow Pipelines v2 component definitions for the retail banking data prep pipeline.

Each function decorated with @dsl.component is a self-contained, containerised step
that can be executed independently (local runner) or as part of the full KFP pipeline.
"""
import os
from kfp import dsl


BASE_IMAGE = os.getenv(
    "PIPELINE_BASE_IMAGE",
    "quay.io/modh/runtime-images:runtime-datascience-ubi9-python-3.9-20241111-3f76685"
)

PACKAGES = [
    "pandas==2.1.4",
    "pyarrow==14.0.2",
    "boto3==1.34.0",
    "great-expectations==0.18.12",
    "ydata-profiling==4.6.4",
    "scikit-learn==1.4.0",
    "faker==22.0.0",
    "sdv==1.9.0",
]


@dsl.component(base_image=BASE_IMAGE, packages_to_install=PACKAGES)
def ingest_data(
    minio_endpoint: str,
    raw_bucket: str,
    use_case: str,
    n_customers: int,
    output_dataset: dsl.Output[dsl.Dataset],
) -> None:
    """
    Phase 1: Generate synthetic data and upload to MinIO raw bucket.

    Generates customer and transaction records using the configured synthetic
    data generators and writes versioned Parquet files to S3.
    """
    import logging
    import os
    import sys

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    os.environ["MINIO_ENDPOINT"] = minio_endpoint

    # Import here to avoid top-level import issues in containerised env
    from src.data_generation.customers import generate_customers
    from src.ingestion.minio_client import upload_dataframe

    logger.info(f"[ingest_data] use_case={use_case}, n_customers={n_customers:,}")

    df = generate_customers(n=n_customers, seed=42)
    key = f"customers/use_case={use_case}/v=1/customers.parquet"
    uri = upload_dataframe(df, bucket=raw_bucket, key=key)

    # Write the URI to the output artifact for downstream components
    with open(output_dataset.path, "w") as f:
        f.write(uri)

    logger.info(f"[ingest_data] Done — {len(df):,} rows at {uri}")


@dsl.component(base_image=BASE_IMAGE, packages_to_install=PACKAGES)
def run_eda(
    input_dataset: dsl.Input[dsl.Dataset],
    reports_bucket: str,
    run_id: str,
    profile_report: dsl.Output[dsl.Artifact],
) -> None:
    """
    Phase 2: Exploratory data analysis and profiling.

    Generates a ydata-profiling HTML report and uploads to the reports bucket.
    Key statistics (nulls, cardinality, skewness) are logged for MLflow tracking.
    """
    import logging
    from ydata_profiling import ProfileReport
    from src.ingestion.minio_client import download_dataframe, upload_file
    import pandas as pd

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    with open(input_dataset.path) as f:
        s3_uri = f.read().strip()

    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    df = download_dataframe(bucket=bucket, key=key)

    logger.info(f"[run_eda] Profiling {len(df):,} rows, {df.shape[1]} columns")

    profile = ProfileReport(
        df,
        title=f"Data Profile — Run {run_id}",
        explorative=True,
        minimal=False,
    )

    local_path = f"/tmp/profile_{run_id}.html"
    profile.to_file(local_path)

    report_key = f"reports/eda/{run_id}/profile.html"
    uri = upload_file(local_path, bucket=reports_bucket, key=report_key)

    with open(profile_report.path, "w") as f:
        f.write(uri)

    logger.info(f"[run_eda] Profile saved to {uri}")


@dsl.component(base_image=BASE_IMAGE, packages_to_install=PACKAGES)
def clean_and_transform(
    input_dataset: dsl.Input[dsl.Dataset],
    processed_bucket: str,
    run_id: str,
    output_dataset: dsl.Output[dsl.Dataset],
) -> None:
    """
    Phase 3: Data cleaning and transformation.

    Applies: null imputation, outlier clipping (3-sigma), categorical encoding,
    and feature derivation. All transformations are deterministic and logged.
    """
    import logging
    import numpy as np
    import pandas as pd
    from src.ingestion.minio_client import download_dataframe, upload_dataframe

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    with open(input_dataset.path) as f:
        s3_uri = f.read().strip()

    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    df = download_dataframe(bucket=bucket, key=key)
    original_len = len(df)

    logger.info(f"[clean_and_transform] Input: {original_len:,} rows")

    # 1. Drop duplicate primary keys
    df = df.drop_duplicates(subset="customer_id")

    # 2. Clip numerical outliers at 3-sigma
    for col in ["annual_income", "credit_score"]:
        if col in df.columns:
            mu, sigma = df[col].mean(), df[col].std()
            df[col] = df[col].clip(mu - 3 * sigma, mu + 3 * sigma)

    # 3. Fill nulls
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    num_cols = df.select_dtypes(include="number").columns.tolist()

    for col in cat_cols:
        df[col] = df[col].fillna("Unknown")
    for col in num_cols:
        df[col] = df[col].fillna(df[col].median())

    # 4. Derived features
    if "annual_income" in df.columns and "num_products" in df.columns:
        df["income_per_product"] = df["annual_income"] / df["num_products"].clip(1)

    if "months_with_bank" in df.columns:
        df["tenure_years"] = df["months_with_bank"] / 12.0

    if "credit_score" in df.columns:
        df["credit_tier"] = pd.cut(
            df["credit_score"],
            bins=[0, 499, 579, 669, 739, 799, 850],
            labels=["Very Poor", "Poor", "Fair", "Good", "Very Good", "Excellent"],
        )

    removed = original_len - len(df)
    logger.info(
        f"[clean_and_transform] Output: {len(df):,} rows "
        f"(removed {removed:,} duplicates)"
    )

    out_key = f"customers_clean/run_id={run_id}/customers_clean.parquet"
    uri = upload_dataframe(df, bucket=processed_bucket, key=out_key)

    with open(output_dataset.path, "w") as f:
        f.write(uri)


@dsl.component(base_image=BASE_IMAGE, packages_to_install=PACKAGES)
def validate_quality(
    input_dataset: dsl.Input[dsl.Dataset],
    reports_bucket: str,
    suite_name: str,
    run_id: str,
    validation_result: dsl.Output[dsl.Artifact],
) -> bool:
    """
    Phase 4: Data quality validation using Great Expectations.

    Validates the cleaned dataset against a defined Expectation Suite.
    Raises RuntimeError if any critical expectations fail — pipeline halts.

    Returns:
        True if all expectations pass.
    """
    import json
    import logging
    import great_expectations as gx
    import pandas as pd
    from src.ingestion.minio_client import download_dataframe, upload_file

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    with open(input_dataset.path) as f:
        s3_uri = f.read().strip()

    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    df = download_dataframe(bucket=bucket, key=key)

    context = gx.get_context()
    datasource = context.sources.add_pandas(name="pipeline_source")
    asset = datasource.add_dataframe_asset(name="cleaned_customers")
    batch = asset.build_batch_request(dataframe=df)
    validator = context.get_validator(
        batch_request=batch,
        expectation_suite_name=suite_name
    )

    # Schema
    validator.expect_column_to_exist("customer_id")
    validator.expect_column_values_to_not_be_null("customer_id")
    validator.expect_column_values_to_be_unique("customer_id")

    # Business rules
    validator.expect_column_values_to_be_between("credit_score", min_value=300, max_value=850)
    validator.expect_column_values_to_be_between("age", min_value=18, max_value=100)
    validator.expect_column_values_to_be_in_set("gender", value_set=["M", "F", "Unknown"])
    validator.expect_column_values_to_be_in_set("churn_flag", value_set=[0, 1])

    # Statistical expectations
    validator.expect_column_mean_to_be_between("churn_flag", min_value=0.05, max_value=0.40)
    validator.expect_column_values_to_be_between("annual_income", min_value=0)

    results = validator.validate()

    # Save validation result
    result_path = f"/tmp/ge_result_{run_id}.json"
    with open(result_path, "w") as f:
        json.dump(results.to_json_dict(), f, indent=2)

    upload_file(result_path, bucket=reports_bucket,
                key=f"reports/ge/{run_id}/validation_result.json")

    with open(validation_result.path, "w") as f:
        f.write(str(results["success"]))

    if not results["success"]:
        failed = [
            r["expectation_config"]["expectation_type"]
            for r in results["results"]
            if not r["success"]
        ]
        raise RuntimeError(
            f"[validate_quality] Data quality FAILED. "
            f"Failed expectations: {failed}"
        )

    logger.info(
        f"[validate_quality] All expectations passed "
        f"({results['statistics']['successful_expectations']}/"
        f"{results['statistics']['evaluated_expectations']})"
    )
    return True


@dsl.component(base_image=BASE_IMAGE, packages_to_install=PACKAGES)
def build_features(
    input_dataset: dsl.Input[dsl.Dataset],
    features_bucket: str,
    use_case: str,
    run_id: str,
    output_features: dsl.Output[dsl.Dataset],
) -> None:
    """
    Phase 5: Feature engineering for a specific use case.

    Builds the ML-ready feature set and writes versioned Parquet to the
    features bucket. Feature definitions are use-case specific.
    """
    import logging
    import numpy as np
    import pandas as pd
    from sklearn.preprocessing import LabelEncoder
    from src.ingestion.minio_client import download_dataframe, upload_dataframe

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    with open(input_dataset.path) as f:
        s3_uri = f.read().strip()

    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    df = download_dataframe(bucket=bucket, key=key)

    logger.info(f"[build_features] use_case={use_case}, input={len(df):,} rows")

    if use_case == "churn":
        # Churn-specific features
        df["product_density"] = df["num_products"] / df["tenure_years"].clip(0.1)
        df["has_multiple_products"] = (df["num_products"] > 1).astype(int)
        feature_cols = [
            "age", "annual_income", "credit_score", "months_with_bank",
            "num_products", "has_loan", "has_credit_card", "has_savings_account",
            "is_active", "income_per_product", "tenure_years",
            "product_density", "has_multiple_products",
        ]
        label_col = "churn_flag"

    elif use_case == "credit_risk":
        df["debt_to_income"] = (df["annual_income"] * 0.3) / df["annual_income"].clip(1)
        feature_cols = [
            "age", "annual_income", "credit_score", "months_with_bank",
            "num_products", "has_loan", "income_per_product", "tenure_years",
        ]
        label_col = "churn_flag"  # proxy; replace with actual default flag

    elif use_case == "fraud":
        feature_cols = [
            "age", "annual_income", "credit_score", "months_with_bank",
            "num_products", "is_active", "income_per_product",
        ]
        label_col = "churn_flag"  # proxy; replace with actual fraud flag

    else:
        raise ValueError(f"Unknown use case: {use_case}")

    # Encode remaining categoricals
    le = LabelEncoder()
    if "governorate" in df.columns:
        df["governorate_enc"] = le.fit_transform(df["governorate"].astype(str))
        feature_cols.append("governorate_enc")

    out_df = df[feature_cols + [label_col]].copy()
    out_df = out_df.dropna()

    out_key = f"{use_case}/run_id={run_id}/features.parquet"
    uri = upload_dataframe(out_df, bucket=features_bucket, key=out_key)

    with open(output_features.path, "w") as f:
        f.write(uri)

    logger.info(
        f"[build_features] Done — {len(out_df):,} rows, "
        f"{len(feature_cols)} features → {uri}"
    )
