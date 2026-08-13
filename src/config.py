"""
Central configuration for the OpenShift AI Data Preparation POC.
All values sourced from environment variables — no hardcoded credentials.
"""
import os
from dataclasses import dataclass, field


@dataclass
class StorageConfig:
    """MinIO / S3-compatible storage configuration."""
    endpoint_url: str = field(
        default_factory=lambda: os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    )
    access_key: str = field(
        default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", "")
    )
    secret_key: str = field(
        default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", "")
    )
    region: str = field(
        default_factory=lambda: os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )

    # Bucket names
    raw_bucket: str = "poc-raw"
    processed_bucket: str = "poc-processed"
    features_bucket: str = "poc-features"
    reports_bucket: str = "poc-reports"


@dataclass
class MLflowConfig:
    """MLflow experiment tracking configuration."""
    tracking_uri: str = field(
        default_factory=lambda: os.getenv(
            "MLFLOW_TRACKING_URI", "http://mlflow:5000"
        )
    )
    experiment_name: str = field(
        default_factory=lambda: os.getenv(
            "MLFLOW_EXPERIMENT_NAME", "retail-banking-data-prep-poc"
        )
    )


@dataclass
class PipelineConfig:
    """Kubeflow Pipelines configuration."""
    endpoint: str = field(
        default_factory=lambda: os.getenv("KFP_ENDPOINT", "")
    )
    namespace: str = field(
        default_factory=lambda: os.getenv("KFP_NAMESPACE", "default")
    )


@dataclass
class DataConfig:
    """Synthetic data generation settings."""
    locale: str = "ar_EG"  # Arabic Egyptian locale for Faker
    random_seed: int = 42

    # Volume targets
    n_customers: int = 500_000
    n_transactions: int = 2_000_000
    n_loans: int = 200_000

    # Class imbalance targets (updated from data scientist schema response)
    fraud_rate: float = 0.012          # 1.2% fraud transactions
    default_rate: float = 0.08         # 8% loan defaults
    churn_rate: float = 0.18           # 18% annual churn


@dataclass
class POCConfig:
    """Top-level configuration container."""
    storage: StorageConfig = field(default_factory=StorageConfig)
    mlflow: MLflowConfig = field(default_factory=MLflowConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    data: DataConfig = field(default_factory=DataConfig)


# Singleton config instance
config = POCConfig()
