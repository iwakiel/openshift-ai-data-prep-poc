# Study Guide — Retail Banking Data Prep POC
# For the sprint review meeting — 1-hour read

---

## Part 1: The datasets explained in plain language

### Why open datasets at all?

You cannot use real Banque Misr customer data in a POC environment. There are two reasons. First, it requires legal, data governance, and privacy approvals that take weeks. Second, a POC's job is to prove the PIPELINE works, not prove the MODEL is accurate — for that, any dataset with the right shape and statistical properties is fine. Real data comes in when the platform is proven.

---

### ULB Credit Card Fraud Detection

**What it is:** In September 2013 a research group at a Belgian university (ULB) collected two months of European credit card transactions — 284,807 in total. They published it publicly after anonymising the data using a mathematical technique called PCA, which scrambles the original column values into 28 numbered columns (V1 through V28) that cannot be reverse-engineered.

**The key number:** Only 492 of those 284,807 transactions are fraudulent. That is 0.17%. Out of every 585 transactions, one is fraud.

**Why you use it:** Not because it represents Egyptian transactions. You use it because it has the exact statistical problem that every fraud detection pipeline must solve: extreme class imbalance. Building a pipeline that handles 0.17% positive class is the engineering challenge. The currency and location are irrelevant.

**Egypt relevance:** Zero, and that is fine. The pipeline handles the imbalance. The actual values inside the columns are meaningless — they are scrambled mathematically. The shape of the problem is universal.

---

### Home Credit Default Risk

**What it is:** A dataset from a Kaggle machine learning competition in 2018. Home Credit is a real financial company that makes consumer loans in emerging markets (Russia, Philippines, Indonesia, etc.) to people without traditional credit histories. They released their data publicly.

**The key number:** 300,000+ loan applications across 7 linked tables: a main application table, bureau credit checks, previous loan history, instalment payment records, credit card balance history, and cash loan balance history.

**Why you use it:** Because your retail bank's credit risk data will have exactly this multi-table structure. There will be a customer table, a loan table, a repayment history table, bureau data from external credit agencies. The engineering challenge — joining these tables, aggregating features across time, handling missing values in some tables — is the same regardless of whether the underlying loans are in Philippine pesos or Egyptian pounds.

**Egypt relevance:** The structure of the problem is directly relevant. The specific country is not.

---

### German Credit Dataset

**What it is:** A dataset from 1994 from a German bank. 1,000 records. Each record is a bank customer with features like employment status, loan purpose, credit history, and age. The binary target is good credit risk vs bad credit risk.

**Why you use it:** It is tiny (1,000 rows), clean, and runs through the entire pipeline in 2 seconds. It is useful only as a fast sanity check — you run the cleaning, validation, and feature engineering code on it to confirm the pipeline doesn't crash, before testing it on the 300,000-row Home Credit data.

**Egypt relevance:** None. You would not present German Credit as a real data strategy. It is a testing tool, like a unit test. When speaking about it in the meeting, you can say: "We also use the German Credit dataset as a lightweight test fixture for pipeline validation — it runs end-to-end in seconds."

---

### Bank Marketing UCI

**What it is:** Data from a Portuguese bank's telephone marketing campaigns, 2008 to 2013. Bank agents called customers to sell them term deposits (a product where you lock money in a bank for a fixed period at a fixed interest rate). 41,188 calls recorded. The target column is: did the customer subscribe? Yes or no.

**UCI:** Stands for University of California Irvine, which runs a publicly available machine learning dataset repository at archive.ics.uci.edu. It has been running since 1987 and contains hundreds of datasets used in academic research. When you see "UCI dataset" it just means it was donated to that repository and is free to download.

**Why you use it for churn:** The features that predict whether someone buys a term deposit — their account tenure, how many products they have, their balance, how recently they engaged with the bank, macroeconomic conditions — are very similar to the features that predict whether a customer will leave the bank. It is not a perfect proxy, but it is the closest public dataset available to a retail bank churn model.

**Egypt relevance:** The macroeconomic features (Euribor rate, employment variation index) are Portuguese and do not apply. You would replace those with Egyptian equivalents (Central Bank of Egypt overnight rate, etc.) in the real model. For the pipeline POC, they serve as examples of what macroeconomic context columns look like.

---

## Part 2: What Faker is and how it works

Faker is a Python library that generates fake but plausible personal data. You install it, tell it what locale to use, and call it like a function.

```python
from faker import Faker

# English locale (default)
fake = Faker()
fake.name()           # 'Jennifer Collins'
fake.email()          # 'jennifer.collins@example.com'
fake.phone_number()   # '+1-555-0123'
fake.uuid4()          # 'a3f2c1d4-8b5e-4f2a-9c3d-1e7f2a4b8c9d'

# Arabic Egyptian locale
fake = Faker('ar_EG')
fake.name()           # 'محمد أحمد السيد'
fake.phone_number()   # '+2 010 9876 5432'
```

### What ar_EG gives you

When you use `Faker('ar_EG')`:
- Names are Arabic, gender-appropriate (masculine and feminine forms)
- Phone numbers are in Egyptian mobile format (+20 10x, +20 11x, +20 12x)
- Addresses use Egyptian city names and street patterns
- The National ID (14 digits) follows the Egyptian format

### What Faker does NOT know

Faker does not know anything about Egyptian banking. It generates the personal identity layer — names, IDs, phones. All the financial behaviour in the generators is built separately using NumPy statistical distributions:

- Income: log-normal distribution tuned to Egyptian pound ranges (1,500 to 5,000,000 EGP)
- Credit scores: normally distributed around 620, clipped to 300–850
- Churn flag: a logistic model that takes tenure, products, and credit score as inputs and produces roughly 18% churn
- Fraud flag: a logistic model that takes amount, hour, channel, and international flag to produce roughly 1.2% fraud

So Faker generates: name, ID, phone, address.
NumPy generates: income, credit score, balance, behaviour flags.

The combination produces a synthetic customer that looks plausible for an Egyptian retail banking context.

---

## Part 3: What you built in the repo

The repo is at: github.com/iwakiel/openshift-ai-data-prep-poc

### The structure in plain language

```
src/config.py
```
A configuration file that reads environment variables (MinIO endpoint, MLflow URL, etc.) and makes them available as Python objects. No hardcoded values anywhere — all settings come from environment variables.

```
src/data_generation/customers.py
src/data_generation/transactions.py
```
Two scripts that generate synthetic retail banking data. `customers.py` creates 500,000 synthetic Egyptian retail bank customers with realistic demographics and financial profiles. `transactions.py` creates 2 million linked transaction events with a 1.2% fraud rate injected using a statistical model.

Both scripts can be run locally with `--local-only` flag to write files to your machine without needing any cloud infrastructure.

```
src/ingestion/minio_client.py
```
A utility file for talking to MinIO (the S3-compatible object storage inside OpenShift AI). It handles uploading DataFrames as Parquet files, downloading them, listing what's in a bucket, and creating buckets if they don't exist. When running locally, you skip this and use `--local-only` instead.

```
src/validation/expectation_suites.py
```
Two data quality rule sets written using Great Expectations. One for the customer table (checks that credit scores are between 300 and 850, ages are between 18 and 100, the churn rate is between 5% and 40%, etc.). One for the transaction table (checks that fraud rate is between 0.5% and 5%, amounts are positive, channels are valid values, etc.). If any rule fails, the pipeline stops and raises an error.

```
src/pipeline/components.py
src/pipeline/banking_pipeline.py
```
The Kubeflow Pipelines v2 code. `components.py` defines the five pipeline steps (ingest, profile, clean, validate, feature engineering) as containerised functions. `banking_pipeline.py` wires them together and provides a command to compile the pipeline to a YAML file that can be uploaded to the RHOAI dashboard. These require a custom Docker image to run on the cluster — that image is defined in `Dockerfile`.

```
scripts/verify_rhoai_env.sh
```
A shell script that checks all 7 conditions required for the pipeline to run on OpenShift AI: the RHOAI operator version, MinIO storage, the pipeline server (DSPA), workbench images, resource quotas, network policies, and Python package access. Run once per BeyondTrust session.

```
docs/sprint_review.md
```
A single GitHub page with all the architecture diagrams. Designed to be opened during the sprint review call.

---

## Part 4: What you are responsible for as MLOps engineer

The simplest way to explain it: the data scientist decides what to predict and how to evaluate whether the prediction is good. You build the system that delivers clean, reliable data to them and makes their work reproducible.

### You are responsible for:

**The pipeline** — the automated system that takes raw data and produces ML-ready feature datasets. Ingestion, cleaning, validation, feature engineering. The five phases in this repo.

**The infrastructure** — setting up and verifying OpenShift AI, configuring MinIO storage, provisioning the Kubeflow pipeline server, making sure the right Python packages are available.

**Data quality contracts** — the Great Expectations rules that define what "acceptable data" means. If data comes in with a fraud rate of 0% or 50%, something is wrong and the pipeline should refuse to proceed.

**Reproducibility** — every pipeline run is versioned (run_id), every output is stored with a version, every experiment is logged in MLflow. The data scientist should be able to reproduce any result from any date.

**The environment** — making sure data scientists can open a workbench notebook and have the libraries, compute, and data access they need to work.

### You are NOT responsible for:

- Choosing which algorithm (logistic regression vs gradient boosting vs neural network)
- Deciding what the threshold for a "fraud alert" should be
- Evaluating whether the model's AUC-ROC is good enough for production
- Business decisions about what to do when a customer is predicted to churn

You build the highway. The data scientist drives on it.

---

## Part 5: Running this on your personal laptop

Yes, you can run the entire pipeline locally. Here is exactly what works without any cloud infrastructure:

```bash
# 1. Clone the repo
git clone https://github.com/iwakiel/openshift-ai-data-prep-poc.git
cd openshift-ai-data-prep-poc

# 2. Install the package
pip install -e ".[pipeline]"

# 3. Generate 500K synthetic customers (saves to /tmp/customers.parquet)
python -m src.data_generation.customers --local-only --records 500000

# 4. Generate 2M transactions linked to those customers
python -m src.data_generation.transactions \
    --customers-path /tmp/customers.parquet \
    --local-only \
    --records 2000000
```

After running those two commands you have realistic synthetic retail banking data on your machine. The Great Expectations validation suites also run locally with no changes.

What does NOT work locally without extra setup:
- MinIO upload (needs a MinIO server — you can run one with Docker, or skip with --local-only)
- KFP pipeline submission (needs the RHOAI cluster)
- MLflow tracking server (needs a running MLflow server)

### How to present this in the meeting

"I developed and validated the data preparation pipeline locally on my machine while the OpenShift AI environment is pending with the platform team. The data generators, cleaning logic, and Great Expectations validation all run end-to-end today. I generated 500,000 synthetic retail banking customer records and validated them against the data quality suite successfully. Deploying to the RHOAI cluster is the first task of the next sprint once the three infrastructure blockers are resolved."

This is professional, honest, and accurate. Developing locally before deploying to the platform is standard MLOps practice — it is not a workaround.

---

## Part 6: Things you might be asked in the meeting

**"Why are you using foreign datasets instead of our actual data?"**
Because getting real customer data into a POC environment requires data governance approval, legal review, and privacy sign-off. That takes weeks. For a POC, we are proving the pipeline works, not the model accuracy. The pipeline logic — how we join tables, clean data, validate quality, engineer features — is the same regardless of whether the underlying data is European or Egyptian. We will use schema information from the retail data scientist to generate synthetic data that matches our actual column structure.

**"What exactly is Great Expectations?"**
It is a Python library that lets you define data quality rules as code. Think of it as a test suite for your data rather than your code. We define rules like "credit scores must be between 300 and 850" or "the fraud rate must be between 0.5% and 5%". If the data violates any rule, the pipeline stops and raises an error rather than passing bad data to the model training step. This prevents the data scientist from training on corrupted or drifted data.

**"What is Kubeflow Pipelines?"**
It is the orchestration layer inside OpenShift AI. Instead of running your Python scripts manually in a notebook, you define each step of the pipeline as a containerised function, chain them together, and submit the whole thing to run automatically. The pipeline server tracks every run, stores the inputs and outputs of each step, and lets you re-run any version with one click. It is what makes the pipeline reproducible and auditable.

**"When will the pipeline actually run on OpenShift AI?"**
Next sprint. The three blockers are the pipeline server provisioning (DSPA), MinIO connectivity confirmation, and PyPI access. I have the request language ready for the platform team. Once those are resolved, the pipeline compiles to a YAML file that I upload to the RHOAI dashboard and submit.

**"What has the data scientist said about the schema?"**
I sent 15 questions covering column names, data types, value ranges, null rates, and the target class imbalance rates for each model. Awaiting response. Once I have it, I update the generator configuration and produce a first batch aligned to our actual schema.

---

## Part 7: The three-sentence version of what you did this sprint

If someone asks for a quick summary:

"I designed and built the full data preparation pipeline for our retail banking POC on OpenShift AI — five automated phases from ingestion to ML-ready feature output, covering fraud detection, credit risk, and customer churn. The codebase is complete, tested locally, and published on GitHub. The next step is deploying it to the RHOAI cluster once the infrastructure blockers are resolved with the platform team."

---

## Part 8: The single most important thing to remember

You are presenting work you actually did. The code exists. The architecture is real. The pipeline structure is correct. You are not bluffing — you built something concrete this sprint. The meeting is about showing what you built, not proving you can answer every technical question perfectly.

If you do not know the answer to something, say: "Good point — let me confirm that and follow up by end of day." That is a professional answer and it is always better than guessing.
