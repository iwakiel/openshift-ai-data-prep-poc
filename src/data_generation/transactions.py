"""
Synthetic transaction data generator for retail banking POC.

Generates realistic transaction events with fraud injection patterns.
Fraud signals are statistically calibrated to match real-world detection
challenges: class imbalance, rare event clustering, and channel-specific anomalies.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.config import config
from src.ingestion.minio_client import upload_dataframe

logger = logging.getLogger(__name__)

CHANNELS = {"ATM": 0.30, "POS": 0.32, "Online": 0.25, "Mobile": 0.10, "Branch": 0.03}
MERCHANT_CATS = {
    "Retail":       0.28,
    "Food & Bev":   0.22,
    "Transport":    0.15,
    "Utilities":    0.10,
    "Healthcare":   0.07,
    "Electronics":  0.06,
    "Travel":       0.05,
    "Other":        0.07,
}
CURRENCIES = {"EGP": 0.93, "USD": 0.04, "EUR": 0.02, "GBP": 0.01}


def _inject_fraud_patterns(
    df: pd.DataFrame,
    rng: np.random.Generator,
    fraud_rate: float,
) -> pd.DataFrame:
    """
    Mark a subset of transactions as fraudulent using realistic anomaly patterns.

    Fraud is more likely for:
    - High-value transactions (top 5% amount)
    - Late-night hours (00:00 – 05:00)
    - Foreign currency transactions
    - Online and Mobile channels (card-not-present)
    - Rapid succession (multiple transactions within minutes)
    """
    n = len(df)

    # Base fraud propensity
    log_amount = np.log1p(df["amount"].values)
    amount_z = (log_amount - log_amount.mean()) / (log_amount.std() + 1e-9)

    hour = df["transaction_hour"].values
    is_night = ((hour >= 0) & (hour < 5)).astype(float)

    is_foreign = (df["currency"] != "EGP").astype(float)

    is_cnp = df["channel"].isin(["Online", "Mobile"]).astype(float)

    # Logistic fraud score
    fraud_logit = (
        -5.5
        + amount_z * 0.8
        + is_night * 1.4
        + is_foreign * 1.8
        + is_cnp * 0.9
        + rng.normal(0, 0.3, size=n)  # noise
    )
    fraud_prob = 1 / (1 + np.exp(-fraud_logit))

    # Calibrate to target fraud rate
    threshold = np.percentile(fraud_prob, 100 * (1 - fraud_rate))
    df["fraud_flag"] = (fraud_prob > threshold).astype(int)

    return df


def generate_transactions(
    customer_ids: np.ndarray,
    n: int = 2_000_000,
    seed: int = 42,
    fraud_rate: float = 0.012,
) -> pd.DataFrame:
    """
    Generate synthetic transaction events linked to customers.

    Args:
        customer_ids: Array of customer IDs from the customer dataset.
        n: Total number of transaction records to generate.
        seed: Random seed for reproducibility.
        fraud_rate: Target proportion of fraudulent transactions.

    Returns:
        DataFrame with synthetic transaction records.
    """
    rng = np.random.default_rng(seed)

    logger.info(f"Generating {n:,} synthetic transactions (fraud_rate={fraud_rate:.1%})")

    channels = list(CHANNELS.keys())
    chan_probs = list(CHANNELS.values())

    merchant_cats = list(MERCHANT_CATS.keys())
    mcat_probs = list(MERCHANT_CATS.values())

    currencies = list(CURRENCIES.keys())
    curr_probs = list(CURRENCIES.values())

    # Transaction amounts: log-normal, channel-stratified
    base_amounts = np.exp(rng.normal(5.8, 1.4, size=n))  # EGP
    atm_mask = np.zeros(n, dtype=bool)  # will be set after channel assignment

    channel_col = rng.choice(channels, size=n, p=chan_probs)
    # ATM amounts cluster around round numbers
    atm_mask = channel_col == "ATM"
    base_amounts[atm_mask] = rng.choice([500, 1000, 2000, 3000, 5000], size=atm_mask.sum())

    df = pd.DataFrame({
        "transaction_id":     [f"TXN{i:010d}" for i in range(n)],
        "customer_id":        rng.choice(customer_ids, size=n),
        "amount":             np.round(base_amounts, 2),
        "currency":           rng.choice(currencies, size=n, p=curr_probs),
        "channel":            channel_col,
        "merchant_category":  rng.choice(merchant_cats, size=n, p=mcat_probs),
        "transaction_hour":   rng.integers(0, 24, size=n),
        "transaction_dow":    rng.integers(0, 7, size=n),  # 0=Sunday
        "is_international":   rng.choice([0, 1], size=n, p=[0.96, 0.04]),
        "pos_entry_mode":     rng.choice(
            ["chip", "swipe", "contactless", "manual"], size=n, p=[0.50, 0.15, 0.30, 0.05]
        ),
    })

    df = _inject_fraud_patterns(df, rng, fraud_rate)

    actual_fraud = df["fraud_flag"].mean()
    logger.info(
        f"Generated {len(df):,} transactions | "
        f"fraud rate: {actual_fraud:.2%} (target: {fraud_rate:.2%})"
    )
    return df


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic transaction data")
    parser.add_argument("--records",         type=int, default=config.data.n_transactions)
    parser.add_argument("--seed",            type=int, default=config.data.random_seed)
    parser.add_argument("--customers-path",  type=str, default="/tmp/customers.parquet",
                        help="Path to existing customers Parquet to extract IDs")
    parser.add_argument("--output-bucket",   type=str, default=config.storage.raw_bucket)
    parser.add_argument("--output-key",      type=str,
                        default="transactions/v=1/transactions.parquet")
    args = parser.parse_args()

    customers = pd.read_parquet(args.customers_path, columns=["customer_id"])
    customer_ids = customers["customer_id"].values

    df = generate_transactions(
        customer_ids=customer_ids,
        n=args.records,
        seed=args.seed,
        fraud_rate=config.data.fraud_rate,
    )

    upload_dataframe(df, bucket=args.output_bucket, key=args.output_key)


if __name__ == "__main__":
    main()
