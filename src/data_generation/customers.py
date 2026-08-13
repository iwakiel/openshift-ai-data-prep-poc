"""
Synthetic customer data generator for retail banking POC.

Generates realistic customer records with demographics, account attributes,
and financial profile fields. No real customer data is used or referenced.
All values are synthetically generated using Faker and NumPy distributions.
"""
import argparse
import logging
import os
from typing import Optional

import numpy as np
import pandas as pd
from faker import Faker

from src.config import config
from src.ingestion.minio_client import upload_dataframe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


GOVERNORATES = {
    "Cairo":        0.30,
    "Giza":         0.18,
    "Alexandria":   0.14,
    "Qalyubia":     0.08,
    "Sharqia":      0.06,
    "Dakahlia":     0.06,
    "Gharbia":      0.05,
    "Monufia":      0.04,
    "Beheira":      0.04,
    "Other":        0.05,
}

CUSTOMER_SEGMENTS = {
    "Mass":         0.55,
    "Emerging":     0.25,
    "Affluent":     0.15,
    "Private":      0.05,
}

PRODUCT_COUNTS = {1: 0.35, 2: 0.28, 3: 0.20, 4: 0.10, 5: 0.05, 6: 0.02}


def generate_customers(
    n: int = 500_000,
    seed: int = 42,
    locale: str = "ar_EG",
    churn_rate: float = 0.18,
) -> pd.DataFrame:
    """
    Generate a synthetic customer dataset for retail banking POC.

    Args:
        n: Number of customer records to generate.
        seed: Random seed for reproducibility.
        locale: Faker locale for name and address generation.
        churn_rate: Target proportion of churned customers.

    Returns:
        DataFrame with synthetic customer records.
    """
    rng = np.random.default_rng(seed)
    fake = Faker(locale)
    Faker.seed(seed)

    logger.info(f"Generating {n:,} synthetic customer records (locale={locale})")

    governorates = list(GOVERNORATES.keys())
    gov_probs = list(GOVERNORATES.values())

    segments = list(CUSTOMER_SEGMENTS.keys())
    seg_probs = list(CUSTOMER_SEGMENTS.values())

    prod_counts = list(PRODUCT_COUNTS.keys())
    prod_probs = list(PRODUCT_COUNTS.values())

    # Age distribution: skewed toward working-age population
    ages = np.clip(rng.normal(loc=38, scale=12, size=n).astype(int), 18, 75)

    # Income: log-normal (skewed right), calibrated for local context
    incomes = np.clip(np.exp(rng.normal(10.3, 0.65, size=n)), 1_500, 5_000_000)

    # Credit score: correlated with age and income (simplified)
    base_scores = rng.normal(620, 85, size=n)
    age_boost = (ages - 18) * 0.8
    income_boost = np.log1p(incomes) * 1.5
    credit_scores = np.clip(base_scores + age_boost * 0.3 + income_boost * 0.2, 300, 850).astype(int)

    # Tenure: older customers tend to have longer tenure
    max_tenure_months = np.clip((ages - 18) * 8, 1, 360).astype(int)
    tenure_months = rng.integers(1, max_tenure_months + 1)

    # Product count: more products for higher income / longer tenure
    num_products = rng.choice(prod_counts, size=n, p=prod_probs)

    # Churn flag: higher for shorter tenure, fewer products, lower engagement
    churn_logit = (
        -2.5
        + (tenure_months < 12) * 1.2
        + (num_products == 1) * 0.8
        + (credit_scores < 500) * 0.5
    )
    churn_prob = 1 / (1 + np.exp(-churn_logit))
    # Calibrate to target rate
    threshold = np.percentile(churn_prob, 100 * (1 - churn_rate))
    churn_flag = (churn_prob > threshold).astype(int)

    records = {
        "customer_id":          [fake.uuid4() for _ in range(n)],
        "age":                  ages,
        "gender":               rng.choice(["M", "F"], size=n, p=[0.56, 0.44]),
        "governorate":          rng.choice(governorates, size=n, p=gov_probs),
        "customer_segment":     rng.choice(segments, size=n, p=seg_probs),
        "annual_income":        np.round(incomes, 2),
        "credit_score":         credit_scores,
        "months_with_bank":     tenure_months,
        "num_products":         num_products,
        "has_loan":             rng.choice([0, 1], size=n, p=[0.62, 0.38]),
        "has_credit_card":      rng.choice([0, 1], size=n, p=[0.45, 0.55]),
        "has_savings_account":  rng.choice([0, 1], size=n, p=[0.30, 0.70]),
        "is_active":            rng.choice([0, 1], size=n, p=[0.20, 0.80]),
        "churn_flag":           churn_flag,
    }

    df = pd.DataFrame(records)

    actual_churn = df["churn_flag"].mean()
    logger.info(
        f"Generated {len(df):,} customers | "
        f"churn rate: {actual_churn:.1%} (target: {churn_rate:.1%})"
    )
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic customer data")
    parser.add_argument("--records",       type=int, default=config.data.n_customers)
    parser.add_argument("--seed",          type=int, default=config.data.random_seed)
    parser.add_argument("--output-bucket", type=str, default=config.storage.raw_bucket)
    parser.add_argument("--output-key",    type=str, default="customers/v=1/customers.parquet")
    parser.add_argument("--local-only",    action="store_true", help="Write locally, skip S3 upload")
    args = parser.parse_args()

    df = generate_customers(
        n=args.records,
        seed=args.seed,
        churn_rate=config.data.churn_rate,
    )

    if args.local_only:
        out_path = f"/tmp/{args.output_key.replace('/', '_')}"
        df.to_parquet(out_path, index=False)
        logger.info(f"Saved locally: {out_path} ({len(df):,} rows)")
    else:
        upload_dataframe(df, bucket=args.output_bucket, key=args.output_key)


if __name__ == "__main__":
    main()
