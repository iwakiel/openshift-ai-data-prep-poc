"""
Kubeflow Pipelines v2 component definitions for the retail banking data prep pipeline.

Each component references a custom base image that has the src package pre-installed.
Build and push the image before compiling the pipeline:

    make build-image push-image

Set PIPELINE_IMAGE in your .env to point to the pushed image.
Components can be tested locally by calling their inner logic directly.
"""
import os
from kfp import dsl

PIPELINE_IMAGE = os.getenv(
    "PIPELINE_IMAGE",
    "image-registry.openshift-image-registry.svc:5000/mlops-poc/retail-data-prep:latest",
)


@dsl.component(base_image=PIPELINE_IMAGE)
def ingest_retail_data(
    minio_endpoint: str,
    raw_bucket: str,
    n_customers: int,
    n_transactions: int,
    run_id: str,
    customers_uri: dsl.Output[dsl.Dataset],
    transactions_uri: dsl.Output[dsl.Dataset],
) -> None:
    """Phase 1: Generate synthetic retail banking data and upload to MinIO."""
    import logging, os
    os.environ["MINIO_ENDPOINT"] = minio_endpoint
    from src.data_generation.customers import generate_customers
    from src.data_generation.transactions import generate_transactions
    from src.ingestion.minio_client import upload_dataframe

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Phase 1: data ingestion (run_id=%s)", run_id)

    customers = generate_customers(n=n_customers, seed=42)
    c_uri = upload_dataframe(customers, raw_bucket, f"customers/run_id={run_id}/customers.parquet")

    transactions = generate_transactions(
        customer_ids=customers["customer_id"].values, n=n_transactions, seed=42
    )
    t_uri = upload_dataframe(transactions, raw_bucket, f"transactions/run_id={run_id}/transactions.parquet")

    customers_uri.path = c_uri
    transactions_uri.path = t_uri
    logger.info("Ingested %d customers, %d transactions", len(customers), len(transactions))


@dsl.component(base_image=PIPELINE_IMAGE)
def profile_dataset(
    input_uri: dsl.Input[dsl.Dataset],
    reports_bucket: str,
    dataset_name: str,
    run_id: str,
    report_uri: dsl.Output[dsl.Artifact],
) -> None:
    """Phase 2: Generate a ydata-profiling HTML report and upload to S3."""
    import logging
    from ydata_profiling import ProfileReport
    from src.ingestion.minio_client import download_dataframe, upload_file

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    bucket, key = input_uri.path.replace("s3://", "").split("/", 1)
    df = download_dataframe(bucket=bucket, key=key)
    sample = df.sample(min(50_000, len(df)), random_state=42)

    profile = ProfileReport(sample, title=f"{dataset_name} — run {run_id}", minimal=len(df) > 100_000)
    local_path = f"/tmp/profile_{dataset_name}_{run_id}.html"
    profile.to_file(local_path)

    r_uri = upload_file(local_path, reports_bucket, f"reports/eda/run_id={run_id}/{dataset_name}_profile.html")
    report_uri.path = r_uri
    logger.info("Profile saved: %s", r_uri)


@dsl.component(base_image=PIPELINE_IMAGE)
def clean_retail_data(
    input_uri: dsl.Input[dsl.Dataset],
    processed_bucket: str,
    dataset_name: str,
    run_id: str,
    output_uri: dsl.Output[dsl.Dataset],
) -> None:
    """Phase 3: Deduplication, outlier clipping, null handling, and feature derivation."""
    import logging
    import pandas as pd
    from src.ingestion.minio_client import download_dataframe, upload_dataframe

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    bucket, key = input_uri.path.replace("s3://", "").split("/", 1)
    df = download_dataframe(bucket=bucket, key=key)
    n_in = len(df)

    pk = "customer_id" if "customer_id" in df.columns else "transaction_id"
    df = df.drop_duplicates(subset=pk)

    for col in df.select_dtypes(include="number").columns:
        mu, sigma = df[col].mean(), df[col].std()
        if sigma > 0:
            df[col] = df[col].clip(mu - 3 * sigma, mu + 3 * sigma)
        df[col] = df[col].fillna(df[col].median())

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("Unknown")

    if "annual_income" in df.columns and "num_products" in df.columns:
        df["income_per_product"] = df["annual_income"] / df["num_products"].clip(1)
    if "months_with_bank" in df.columns:
        df["tenure_years"] = (df["months_with_bank"] / 12.0).round(2)
    if "credit_score" in df.columns:
        df["credit_tier"] = pd.cut(
            df["credit_score"],
            bins=[0, 499, 579, 669, 739, 799, 851],
            labels=["very_poor", "poor", "fair", "good", "very_good", "excellent"],
        ).astype(str)

    out_uri = upload_dataframe(df, processed_bucket, f"{dataset_name}_clean/run_id={run_id}/{dataset_name}_clean.parquet")
    output_uri.path = out_uri
    logger.info("Cleaned: %d -> %d rows", n_in, len(df))


@dsl.component(base_image=PIPELINE_IMAGE)
def validate_retail_data(
    input_uri: dsl.Input[dsl.Dataset],
    reports_bucket: str,
    suite_name: str,
    run_id: str,
    result_uri: dsl.Output[dsl.Artifact],
) -> None:
    """Phase 4: Great Expectations validation. Raises RuntimeError on any failure."""
    import json, logging
    from src.ingestion.minio_client import download_dataframe, upload_file
    from src.validation.expectation_suites import validate_dataframe

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    bucket, key = input_uri.path.replace("s3://", "").split("/", 1)
    df = download_dataframe(bucket=bucket, key=key)

    outcome = validate_dataframe(df, suite_name=suite_name, raise_on_failure=True)

    result_path = f"/tmp/ge_{run_id}.json"
    with open(result_path, "w") as f:
        json.dump(outcome, f, indent=2)

    r_uri = upload_file(result_path, reports_bucket, f"reports/ge/run_id={run_id}/{suite_name}.json")
    result_uri.path = r_uri
    logger.info(
        "Validation passed: %d/%d expectations",
        outcome["statistics"]["successful_expectations"],
        outcome["statistics"]["evaluated_expectations"],
    )


@dsl.component(base_image=PIPELINE_IMAGE)
def build_retail_features(
    customers_uri: dsl.Input[dsl.Dataset],
    transactions_uri: dsl.Input[dsl.Dataset],
    features_bucket: str,
    use_case: str,
    run_id: str,
    features_uri: dsl.Output[dsl.Dataset],
) -> None:
    """Phase 5: Join customers + transactions, compute aggregates, output ML-ready Parquet."""
    import logging
    import pandas as pd
    from src.ingestion.minio_client import download_dataframe, upload_dataframe

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    c_bucket, c_key = customers_uri.path.replace("s3://", "").split("/", 1)
    t_bucket, t_key = transactions_uri.path.replace("s3://", "").split("/", 1)
    customers = download_dataframe(bucket=c_bucket, key=c_key)
    transactions = download_dataframe(bucket=t_bucket, key=t_key)

    txn_agg = (
        transactions.groupby("customer_id")
        .agg(
            txn_count=("transaction_id", "count"),
            total_spend=("amount", "sum"),
            avg_txn_amount=("amount", "mean"),
            max_txn_amount=("amount", "max"),
            std_txn_amount=("amount", "std"),
            online_txn_pct=("channel", lambda x: (x == "Online").mean()),
            mobile_txn_pct=("channel", lambda x: (x == "Mobile").mean()),
            night_txn_pct=("transaction_hour", lambda x: ((x >= 0) & (x < 6)).mean()),
            intl_txn_pct=("is_international", "mean"),
            unique_channels=("channel", "nunique"),
            unique_merchants=("merchant_category", "nunique"),
        )
        .reset_index()
    )

    df = customers.merge(txn_agg, on="customer_id", how="left")
    df[txn_agg.columns.drop("customer_id")] = df[txn_agg.columns.drop("customer_id")].fillna(0)

    label_map = {"churn": "churn_flag", "fraud": "fraud_flag", "credit_risk": "churn_flag"}
    label = label_map.get(use_case)

    if use_case == "churn":
        df["product_density"] = df["num_products"] / df["tenure_years"].clip(0.08)
        df["spend_per_product"] = df["total_spend"] / df["num_products"].clip(1)
    elif use_case == "credit_risk":
        df["utilisation_rate"] = df["total_spend"] / df["annual_income"].clip(1)
    elif use_case not in ("fraud", "segmentation"):
        raise ValueError(f"Unknown use case: '{use_case}'")

    meta_cols = ["customer_id", "customer_segment", "governorate"]
    drop_labels = [v for k, v in label_map.items() if k != use_case and v in df.columns]
    exclude = set(meta_cols + drop_labels)
    feature_cols = [c for c in df.columns if c not in exclude]
    out_cols = feature_cols + ([label] if label and label in feature_cols else [])
    out_df = df[out_cols].dropna()

    out_uri = upload_dataframe(out_df, features_bucket, f"{use_case}/run_id={run_id}/features.parquet")
    features_uri.path = out_uri
    logger.info("Features: %d rows, %d columns, use_case=%s", len(out_df), len(out_cols), use_case)
