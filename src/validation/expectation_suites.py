"""
Great Expectations expectation suites for retail banking data contracts.

Each function defines and saves a named expectation suite for a specific
stage of the retail banking data preparation pipeline. Suites are designed
to catch schema drift, business rule violations, and statistical anomalies
before data reaches model training.

Usage:
    from src.validation.expectation_suites import build_customer_suite
    build_customer_suite(context)
"""
import logging
from typing import Optional

import great_expectations as gx
from great_expectations.core import ExpectationSuite

logger = logging.getLogger(__name__)


def build_customer_suite(
    context: gx.DataContext,
    suite_name: str = "retail_banking.customers.v1",
) -> ExpectationSuite:
    """
    Expectation suite for the cleaned customer dataset.

    Covers: schema completeness, business rule constraints, and
    statistical checks calibrated for a retail banking customer base.

    Args:
        context: Initialised Great Expectations DataContext.
        suite_name: Name to register the suite under.

    Returns:
        The saved ExpectationSuite object.
    """
    suite = context.add_or_update_expectation_suite(expectation_suite_name=suite_name)

    datasource = context.sources.add_or_update_pandas(name="customer_validation")
    asset = datasource.add_dataframe_asset(name="customers")

    # Use an empty dataframe just to build the validator for suite definition
    import pandas as pd
    batch = asset.build_batch_request(dataframe=pd.DataFrame())
    validator = context.get_validator(
        batch_request=batch,
        expectation_suite_name=suite_name,
    )

    # -- Schema and completeness --
    for col in ["customer_id", "age", "gender", "annual_income", "credit_score"]:
        validator.expect_column_to_exist(col)
        validator.expect_column_values_to_not_be_null(col)

    validator.expect_column_values_to_be_unique("customer_id")

    # -- Business rules --
    validator.expect_column_values_to_be_between("age", min_value=18, max_value=100)
    validator.expect_column_values_to_be_between(
        "credit_score", min_value=300, max_value=850
    )
    validator.expect_column_values_to_be_between(
        "annual_income", min_value=0
    )
    validator.expect_column_values_to_be_between(
        "num_products", min_value=1, max_value=10
    )
    validator.expect_column_values_to_be_between(
        "months_with_bank", min_value=0
    )
    validator.expect_column_values_to_be_in_set(
        "gender", value_set=["M", "F", "Unknown"]
    )
    validator.expect_column_values_to_be_in_set(
        "churn_flag", value_set=[0, 1]
    )

    # -- Statistical expectations --
    # Churn rate should be within a realistic retail banking range
    validator.expect_column_mean_to_be_between(
        "churn_flag", min_value=0.05, max_value=0.40
    )
    # Active customers should be the majority
    validator.expect_column_mean_to_be_between(
        "is_active", min_value=0.50, max_value=0.98
    )
    # Credit score should cluster around a reasonable mean
    validator.expect_column_mean_to_be_between(
        "credit_score", min_value=550, max_value=720
    )

    validator.save_expectation_suite(discard_failed_expectations=False)
    logger.info(f"Saved expectation suite: {suite_name}")
    return suite


def build_transaction_suite(
    context: gx.DataContext,
    suite_name: str = "retail_banking.transactions.v1",
) -> ExpectationSuite:
    """
    Expectation suite for the cleaned transaction dataset.

    Covers: schema integrity, amount sanity checks, channel validity,
    and fraud rate calibration for retail banking transaction data.

    Args:
        context: Initialised Great Expectations DataContext.
        suite_name: Name to register the suite under.

    Returns:
        The saved ExpectationSuite object.
    """
    suite = context.add_or_update_expectation_suite(expectation_suite_name=suite_name)

    datasource = context.sources.add_or_update_pandas(name="transaction_validation")
    asset = datasource.add_dataframe_asset(name="transactions")

    import pandas as pd
    batch = asset.build_batch_request(dataframe=pd.DataFrame())
    validator = context.get_validator(
        batch_request=batch,
        expectation_suite_name=suite_name,
    )

    # -- Schema and completeness --
    for col in ["transaction_id", "customer_id", "amount", "channel", "fraud_flag"]:
        validator.expect_column_to_exist(col)
        validator.expect_column_values_to_not_be_null(col)

    validator.expect_column_values_to_be_unique("transaction_id")

    # -- Business rules --
    validator.expect_column_values_to_be_between(
        "amount", min_value=0.01
    )
    validator.expect_column_values_to_be_in_set(
        "channel",
        value_set=["ATM", "POS", "Online", "Mobile", "Branch"]
    )
    validator.expect_column_values_to_be_in_set(
        "fraud_flag", value_set=[0, 1]
    )
    validator.expect_column_values_to_be_between(
        "transaction_hour", min_value=0, max_value=23
    )
    validator.expect_column_values_to_be_between(
        "transaction_dow", min_value=0, max_value=6
    )

    # -- Statistical: fraud rate must be within expected range --
    validator.expect_column_mean_to_be_between(
        "fraud_flag", min_value=0.005, max_value=0.05
    )

    validator.save_expectation_suite(discard_failed_expectations=False)
    logger.info(f"Saved expectation suite: {suite_name}")
    return suite


def validate_dataframe(
    df,
    suite_name: str,
    context: Optional[gx.DataContext] = None,
    raise_on_failure: bool = True,
) -> dict:
    """
    Run a named expectation suite against a DataFrame and return the results.

    Args:
        df: pandas DataFrame to validate.
        suite_name: Name of the expectation suite to run.
        context: Optional DataContext. Creates an in-memory context if not provided.
        raise_on_failure: If True, raises RuntimeError on any failed expectation.

    Returns:
        dict with keys: success (bool), statistics (dict), failed (list of str).

    Raises:
        RuntimeError: If raise_on_failure is True and any expectation fails.
    """
    if context is None:
        context = gx.get_context()

    datasource = context.sources.add_or_update_pandas(name="_validation_source")
    asset = datasource.add_dataframe_asset(name="_validation_asset")
    batch = asset.build_batch_request(dataframe=df)

    validator = context.get_validator(
        batch_request=batch,
        expectation_suite_name=suite_name,
    )

    results = validator.validate()

    failed = [
        r["expectation_config"]["expectation_type"]
        for r in results["results"]
        if not r["success"]
    ]

    outcome = {
        "success": bool(results["success"]),
        "statistics": dict(results["statistics"]),
        "failed": failed,
    }

    if raise_on_failure and not outcome["success"]:
        raise RuntimeError(
            f"Data quality validation failed for suite '{suite_name}'. "
            f"Failed expectations: {failed}"
        )

    return outcome
