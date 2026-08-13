"""
MinIO / S3-compatible object storage client for the data preparation POC.

Wraps boto3 with consistent error handling, logging, and Parquet I/O utilities.
All connection parameters are sourced from environment variables.
"""
import io
import logging
import os
from typing import Optional

import boto3
import pandas as pd
from botocore.exceptions import ClientError, EndpointResolutionError

from src.config import config

logger = logging.getLogger(__name__)


def get_s3_client() -> boto3.client:
    """
    Create and return a configured boto3 S3 client pointing to MinIO.

    Returns:
        Configured boto3 S3 client.

    Raises:
        EnvironmentError: If required environment variables are missing.
    """
    endpoint = config.storage.endpoint_url
    access_key = config.storage.access_key
    secret_key = config.storage.secret_key

    if not all([endpoint, access_key, secret_key]):
        raise EnvironmentError(
            "Missing required environment variables: "
            "MINIO_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
        )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=config.storage.region,
    )


def ensure_bucket(bucket: str, client: Optional[boto3.client] = None) -> None:
    """
    Create an S3 bucket if it does not already exist.

    Args:
        bucket: Bucket name to create.
        client: Optional pre-configured boto3 client.
    """
    s3 = client or get_s3_client()
    try:
        s3.head_bucket(Bucket=bucket)
        logger.debug(f"Bucket '{bucket}' already exists.")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            s3.create_bucket(Bucket=bucket)
            logger.info(f"Created bucket: {bucket}")
        else:
            raise


def upload_dataframe(
    df: pd.DataFrame,
    bucket: str,
    key: str,
    client: Optional[boto3.client] = None,
    format: str = "parquet",
) -> str:
    """
    Upload a pandas DataFrame to S3/MinIO as Parquet or CSV.

    Args:
        df: DataFrame to upload.
        bucket: Destination bucket name.
        key: Object key (path within bucket).
        client: Optional pre-configured boto3 client.
        format: Output format — 'parquet' (default) or 'csv'.

    Returns:
        S3 URI of the uploaded object: s3://<bucket>/<key>
    """
    s3 = client or get_s3_client()
    ensure_bucket(bucket, client=s3)

    buf = io.BytesIO()
    if format == "parquet":
        df.to_parquet(buf, index=False, engine="pyarrow", compression="snappy")
    elif format == "csv":
        df.to_csv(buf, index=False)
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'parquet' or 'csv'.")

    buf.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
    uri = f"s3://{bucket}/{key}"
    logger.info(f"Uploaded {len(df):,} rows → {uri}")
    return uri


def download_dataframe(
    bucket: str,
    key: str,
    client: Optional[boto3.client] = None,
    columns: Optional[list] = None,
) -> pd.DataFrame:
    """
    Download a Parquet object from S3/MinIO as a pandas DataFrame.

    Args:
        bucket: Source bucket name.
        key: Object key to download.
        client: Optional pre-configured boto3 client.
        columns: Optional list of columns to read (projection pushdown).

    Returns:
        DataFrame with contents of the S3 object.
    """
    s3 = client or get_s3_client()
    response = s3.get_object(Bucket=bucket, Key=key)
    buf = io.BytesIO(response["Body"].read())
    df = pd.read_parquet(buf, columns=columns)
    logger.info(f"Downloaded {len(df):,} rows from s3://{bucket}/{key}")
    return df


def upload_file(
    local_path: str,
    bucket: str,
    key: str,
    client: Optional[boto3.client] = None,
) -> str:
    """
    Upload a local file to S3/MinIO.

    Args:
        local_path: Path to local file.
        bucket: Destination bucket.
        key: Destination object key.
        client: Optional pre-configured boto3 client.

    Returns:
        S3 URI of the uploaded object.
    """
    s3 = client or get_s3_client()
    ensure_bucket(bucket, client=s3)
    s3.upload_file(local_path, bucket, key)
    uri = f"s3://{bucket}/{key}"
    logger.info(f"Uploaded {local_path} → {uri}")
    return uri


def list_objects(
    bucket: str,
    prefix: str = "",
    client: Optional[boto3.client] = None,
) -> list[str]:
    """
    List object keys in a bucket with an optional prefix filter.

    Args:
        bucket: Bucket to list.
        prefix: Key prefix filter.
        client: Optional pre-configured boto3 client.

    Returns:
        List of object key strings.
    """
    s3 = client or get_s3_client()
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys
