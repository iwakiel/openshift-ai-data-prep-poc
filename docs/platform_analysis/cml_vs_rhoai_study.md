# CML vs RHOAI — Personal Study Guide
# For Wakiel — read this before the manager conversation

This document explains what both platforms actually are, what the research shows,
and what your former and new managers are each right about. It is written to be
understood without deep prior knowledge of either platform.

---

## 1. What you are actually comparing

The comparison is between:

**Cloudera AI** (formerly called Cloudera Machine Learning, or CML — renamed in early 2026
but still called CML in most documentation and in practice at most organisations including
Banque Misr)

versus

**Red Hat OpenShift AI** (RHOAI, formerly called Red Hat OpenShift Data Science / RHODS —
this is the platform you are building the POC on)

Before the comparison starts, here is the single most important fact that most people
in this debate miss:

**CML does not compete with OpenShift. CML runs ON TOP of OpenShift.**

Cloudera's own documentation states explicitly that CML runs on "Red Hat OpenShift Container
Platform (OCP) versions 4.10 or 4.8" and that "CML enables easy onboarding of a new tenant
and provision of an ML workspace in a shared Red Hat OpenShift Container Platform environment."

Red Hat and Cloudera even published a joint blog in November 2025 about running "Cloudera AI
on Red Hat OpenShift" as a combined product.

This means the real comparison at Banque Misr is:
- Option A: Run Cloudera AI (CML) on top of the bank's existing OpenShift cluster
- Option B: Run Red Hat OpenShift AI natively on the same OpenShift cluster

Both run on OpenShift. The question is what software layer sits above it.

---

## 2. What CML actually is — full explanation

CML is not a standalone product. It is one service within the **Cloudera Data Platform (CDP)**.
CDP is a large integrated suite that includes:

- CML (machine learning workspaces and experiments)
- CDE — Cloudera Data Engineering (Spark pipelines with Airflow orchestration)
- CDW — Cloudera Data Warehouse (SQL analytics with Hive and Impala)
- CDF — Cloudera Data Flow (real-time data streaming with Kafka and NiFi)
- SDX — Shared Data Experience (unified security and governance layer)

When your former manager says "CML is better," what they may really mean is "the entire
Cloudera ecosystem integrated together is better than OpenShift AI alone." That is a
different and stronger claim.

**What CML provides specifically:**

Sessions: interactive notebooks where data scientists run code (Python, R, Scala).
Similar to Jupyter but within the CML environment.

Jobs: scheduled or on-demand script execution. Used to automate data pipelines,
model retraining, and drift monitoring.

Experiments: track and compare model training runs. Similar to MLflow experiments.

Models: deploy trained models as REST API endpoints with one click.

Applications: deploy web-based front-ends (Flask, Streamlit, Shiny) that end users
can interact with, built on top of models.

Runtime: the container image that runs inside CML sessions. Since January 2025,
CML uses JupyterLab as the default IDE (replacing the older CDSW interface).

AMPs (Applied ML Prototypes): 130+ one-click deployable machine learning project
templates that Cloudera ships. You click a button and a full end-to-end ML project
deploys in your workspace in minutes. This is genuinely useful for rapid prototyping.

**What CML needs to run:**

This is where the capacity problem comes from. Minimum requirements per workspace:
- 128 GB RAM (recommended: 256 GB)
- 32 CPU cores (recommended: 32-48 cores)
- 4 TB block storage per workspace
- 1 TB NFS space per workspace

A "workspace" in CML is the shared environment for a team. If Banque Misr has one
workspace and it is at capacity, that means all the CPU and RAM allocated to that
workspace are being used by active sessions. New sessions cannot start until existing
ones stop.

**The SDX governance layer:**

This is CML's genuinely strong differentiator. SDX consists of:

Apache Ranger: fine-grained access control. You can say "data scientist A can read
column X but not column Y in table Z." This is table and column-level security,
which is critical in banking for PII protection.

Apache Atlas: data lineage and auditing. It tracks where every piece of data came
from, who accessed it, how it was transformed, and what models were trained on it.
This produces an audit trail that compliance and regulators can inspect.

This governance layer wraps around the entire CDP ecosystem, not just CML. So when
a data scientist in CML trains a model on a dataset, Atlas records that linkage
automatically.

---

## 3. What RHOAI actually is — full explanation

RHOAI is a set of operators and services installed on top of an existing OpenShift
(Kubernetes) cluster. It does not require any additional infrastructure beyond what
OpenShift already runs on.

**What RHOAI provides:**

Workbenches: Jupyter notebook environments running in containers on OpenShift.
Each workbench is isolated with its own resource profile (CPU, GPU, RAM).
Multiple runtime images available: standard data science, PyTorch, TensorFlow, Spark.

Data Science Pipelines (DSPA): managed Kubeflow Pipelines v2 server. This is what
this project uses. Define pipeline steps in Python, compile to YAML, submit to the
DSPA server. Full run history, artifact tracking, scheduling.

Model Serving (KServe / ModelMesh): deploy trained models for inference. KServe
handles single large models; ModelMesh handles many smaller models efficiently.

MLflow: experiment tracking. Every training run logs parameters, metrics, and
artifacts. Compare runs across experiments.

TrustyAI: model monitoring for bias and data drift. Added in RHOAI 2.15
(November 2024). Monitors deployed models in real-time, detects when incoming data
deviates from training data distribution. Important for regulated environments.

Model Registry: added in RHOAI 2.15. Centralised catalogue of trained models with
versions, metadata, and deployment status.

**What RHOAI does NOT include (that CML has):**

- Native Spark integration: RHOAI workbenches can run PySpark, but there is no
  managed Spark cluster manager. You need to configure Spark separately or use
  an operator like Spark Operator for Kubernetes.

- Built-in orchestration like Airflow: RHOAI uses Kubeflow Pipelines (KFP) for
  orchestration, not Airflow. KFP is more ML-focused but less flexible for complex
  data engineering DAGs than Airflow.

- Apache Ranger governance: RHOAI inherits OpenShift's RBAC (role-based access
  control) and namespace isolation, but does not have column-level data access
  control the way Ranger does.

- AMPs equivalent: there are no one-click ML project templates like Cloudera's AMPs.
  You build from scratch or use the Red Hat marketplace.

---

## 4. The Banque Misr context

Based on what you have described:

Banque Misr already has OpenShift running (since CML runs on OpenShift, the bank
has OpenShift as the underlying infrastructure).

CML is deployed on top of that OpenShift cluster and is "fully utilized" — meaning
the workspace has hit its resource limits and users are experiencing contention.

You are now building a POC for RHOAI on the same or similar OpenShift infrastructure.

The strategic question is: should the bank pay for Cloudera CDP licensing to run
CML on OpenShift, or should it use Red Hat's RHOAI which is included in the
OpenShift subscription or available as a lower-cost add-on?

---

## 5. Dimension-by-dimension comparison

### Pipeline orchestration

CML: uses Apache Airflow via CDE (Cloudera Data Engineering). Airflow is the
industry-standard data pipeline orchestrator. It handles complex dependencies,
retry logic, scheduling, and DAG-based workflows. When you need to chain a Spark
job into a data quality check into a model retraining job, Airflow does this
naturally. The CML Airflow operator lets you trigger CML jobs from within an Airflow DAG.

RHOAI: uses Kubeflow Pipelines v2 (KFP). KFP is more specifically designed for ML
workflows — each step is a containerised Python function. KFP has strong ML lineage
and artifact tracking. It is less flexible than Airflow for complex data engineering
dependencies (branching logic, conditional execution, macros are harder to implement),
but for straight ML pipeline sequences it works well and is more reproducible.

Verdict: Airflow (CML) is more powerful for complex data engineering workflows.
KFP (RHOAI) is more purpose-built for ML pipeline reproducibility.

---

### Spark integration

CML: native Spark-on-Kubernetes support. Data scientists can spin up a Spark
session directly from their CML session with one call. The cluster scales up and
down automatically. This is deeply integrated with the Hive Metastore and CDW.

RHOAI: PySpark works in workbench notebooks, but there is no managed Spark cluster.
You can install the Spark Operator for Kubernetes separately and use it via KFP
pipeline steps, but it requires additional setup. For teams doing heavy distributed
data processing, this gap matters.

Verdict: CML wins clearly on Spark. If the retail banking use cases involve
processing billions of transactions on Spark, this is a meaningful advantage.

---

### Data governance

CML (via Cloudera SDX): Apache Ranger for column-level access control + Apache Atlas
for full data lineage. When a data scientist accesses a customer table in CML,
Atlas records who accessed it, when, what query was run, and what model was trained
on it. Ranger can block specific columns from specific users. This is essential for
banking where customer PII must be controlled at the column level (e.g., a data
scientist can use age and income for model training but must not see NID or name).

RHOAI: namespace isolation at the Kubernetes level (different teams have different
projects/namespaces). RBAC controls who can access which workbench. But there is
no built-in column-level data access control equivalent to Ranger, and no automatic
data lineage tracking equivalent to Atlas.

Verdict: CML/Cloudera SDX wins significantly on governance. For a regulated bank
where CBE (Central Bank of Egypt) and internal compliance require knowing exactly
who accessed what data, SDX provides audit evidence that RHOAI alone cannot.

---

### Model monitoring and drift detection

CML: native model metrics capability. Track custom metrics per prediction. Evidently.ai
integration available as an AMP for visualising drift. Jobs can automatically
trigger model retraining when drift is detected. Has been available since 2020.

RHOAI: TrustyAI added in November 2024 (RHOAI 2.15). Provides data drift detection
and bias monitoring for deployed models. Also includes fairness metrics, which
CML does not have natively. The bias detection is specifically important for
regulated industries to prove models are not discriminating on protected attributes.

Verdict: CML has a more mature monitoring setup for traditional ML metrics and drift.
RHOAI's TrustyAI adds fairness/bias monitoring that CML does not have natively,
which is increasingly required by financial regulators.

---

### Model serving

CML: one-click deployment of models as REST endpoints. Scales automatically.
Simple to use for data scientists. Supports Python models directly.

RHOAI: KServe for large single models (including LLMs with vLLM runtime),
ModelMesh for many smaller models deployed efficiently. Supports gRPC and REST.
vLLM serving added in 2.15 for generative AI models. More sophisticated but
also more complex to configure.

Verdict: RHOAI wins for modern serving infrastructure, especially for GenAI models.
CML is simpler for traditional ML model deployment.

---

### Generative AI and LLM capabilities

CML: Cloudera Copilot (code assistant integrated into CML). Integration with
130 Hugging Face models. AMPs for RAG (retrieval-augmented generation) applications.

RHOAI: vLLM runtime for serving LLMs, LoRA fine-tuning support, Nvidia NIM support,
AMD GPU support. More infrastructure-level GenAI capabilities.

Verdict: RHOAI has more robust GenAI infrastructure. CML has more accessible
GenAI templates via AMPs.

---

### Resource requirements and capacity

CML: minimum 128 GB RAM and 32 CPU cores per workspace. 4 TB block storage.
Very heavy footprint. This is why it is fully utilized — once you hit those
resource limits, users wait.

RHOAI: lighter base footprint. Workbench resources are defined per-session via
resource profiles (e.g., small: 2 CPU / 8 GB, large: 4 CPU / 16 GB). The cluster
total resources are shared more efficiently because idle workbenches do not hold
resources.

Verdict: RHOAI is more resource-efficient and scales better on constrained infrastructure.
The capacity problem your former manager is experiencing with CML is partly a product
design issue, not just an infrastructure limitation.

---

### Cost model

CML / Cloudera CDP: pricing starts at approximately £97,776 per year for a 100 TB
platform. Public cloud pricing starts at $0.07 per CCU (Cloudera Compute Unit) per hour.
This is a significant additional licensing cost on top of the OpenShift subscription.

RHOAI: RHOAI is delivered as an operator within the Red Hat OpenShift subscription.
If the bank already pays for OpenShift (which it does, since CML runs on it), RHOAI
may already be included or available at a significantly lower additional cost than
the full Cloudera CDP license.

Verdict: RHOAI wins clearly on cost if the bank already has OpenShift.

---

### Open source and vendor lock-in

CML: the core platform is Cloudera's proprietary software. Apache components
(Ranger, Atlas, Spark, Airflow) are open source but the orchestration and management
layer is Cloudera's. Moving away from Cloudera is non-trivial.

RHOAI: built entirely on open source components — Kubeflow, MLflow, TrustyAI,
KServe, Prometheus, vLLM. Red Hat provides support and hardening, but you can
run all the same components on plain Kubernetes without a Red Hat subscription.
Vendor lock-in is minimal.

Verdict: RHOAI wins on open source and portability.

---

### Compliance certifications

CML / Cloudera SDX: compliant with GDPR, HIPAA through data governance controls.
Apache Ranger is used in many regulated industries.

RHOAI: OpenShift AI has alignment with FedRAMP, HIPAA, PCI DSS, and NIST 800-53.
Red Hat specifically published guidance on banking digital sovereignty (December 2025).
A European bank case study showed 40% reduction in deployment bottleneck times with
RHOAI while maintaining strict regulatory compliance.

Verdict: Both cover compliance. RHOAI has more explicit banking and public sector
compliance framework alignment as of 2025.

---

## 6. What each manager is right about

**Your former manager is right that:**

CML's integrated Cloudera ecosystem — SDX governance, native Spark, Airflow
orchestration, CDE for data engineering — is more complete and battle-tested for
enterprise data platforms that need to run everything from raw data ingestion to
model deployment in one integrated stack. If Banque Misr is already deeply invested
in Cloudera (Hive Metastore, CDW for SQL analytics, CDE for Spark pipelines), then
moving ML workloads to RHOAI creates integration work. CML's audit trail via Apache
Atlas is production-ready for banking compliance in a way that RHOAI is not yet.

**Your former manager's position is weakened by:**

The capacity problem is a real architectural limitation of CML's workspace model.
The additional licensing cost of the full Cloudera CDP stack is significant.
CML's governance advantage only holds if the bank is using the full CDP stack —
if it is using only CML in isolation, SDX governance may not be fully active.

**Your new manager is right that:**

RHOAI is the more cost-effective path if the bank already has OpenShift.
RHOAI's open-source foundation means lower vendor lock-in risk.
RHOAI 2.15 closed several capability gaps (model registry, drift detection,
bias monitoring) that previously favoured CML.
For an MLOps engineer, RHOAI's Kubernetes-native approach is more portable and
more aligned with industry standards.

**Your new manager's position is weakened by:**

RHOAI alone does not solve the Spark integration or the column-level governance
gaps. If the bank needs heavy Spark processing and deep compliance audit trails,
RHOAI alone is not sufficient without additional components.

---

## 7. Your role as MLOps engineer on each platform

On CML your job would be:
- Managing CML workspaces, runtime images, and resource profiles
- Building and scheduling CML Jobs for automated pipelines
- Integrating with CDE (Cloudera Data Engineering) for Spark pipelines
- Configuring and maintaining SDX governance policies
- Monitoring models via CML's native metrics interface
- Deploying models as REST endpoints within CML

On RHOAI your job is:
- Managing workbench environments and resource profiles
- Building KFP v2 pipelines (what this project does)
- Configuring MinIO for S3 storage and MLflow for experiment tracking
- Deploying models via KServe
- Configuring TrustyAI for drift and bias monitoring
- Building and pushing Docker images for pipeline components

The skills are transferable but not identical. KFP and Airflow both model
pipelines as directed acyclic graphs but the APIs and debugging patterns differ.

---

## 8. The strategic answer for Banque Misr

Neither platform is objectively better. The right answer depends on:

1. Does the bank use the full Cloudera CDP stack (CDW, CDE, CDF) or only CML?
   If only CML, then paying for the full CDP license to get just the ML workspace
   is poor value compared to RHOAI.

2. Is column-level data governance via Apache Ranger already active and in use?
   If yes, moving to RHOAI requires replacing that governance layer.
   If no, RHOAI's namespace-level isolation may be sufficient.

3. Is native Spark-on-K8s a hard requirement for the ML use cases?
   For fraud detection and credit risk at scale, processing billions of transactions
   with Spark may be unavoidable. If so, CML's Spark integration is a real advantage.

4. Is the capacity problem solvable by adding resources to the CML workspace?
   If infrastructure can be expanded, the capacity issue is not a reason to switch platforms.
   If infrastructure is fixed, RHOAI's lighter footprint is a practical advantage.

5. What is the procurement reality?
   If the Cloudera license renewal is coming up and RHOAI is included in the existing
   Red Hat subscription, the financial case for RHOAI may be decisive.

---

## 9. Glossary

CDW: Cloudera Data Warehouse — SQL analytics service in CDP using Hive and Impala

CDE: Cloudera Data Engineering — Spark and Airflow service in CDP

CDP: Cloudera Data Platform — the full Cloudera product suite

KFP: Kubeflow Pipelines — the pipeline orchestration system built into RHOAI

KServe: Kubernetes-native model serving platform built into RHOAI

RBAC: Role-Based Access Control — controlling who can do what in a system

SDX: Shared Data Experience — Cloudera's unified governance layer (Ranger + Atlas)

TrustyAI: open-source toolkit for AI fairness and monitoring, built into RHOAI 2.15

vLLM: open-source inference engine for large language models, supported by RHOAI

AMPs: Applied ML Prototypes — one-click ML project templates in Cloudera
