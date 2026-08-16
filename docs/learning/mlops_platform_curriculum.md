# MLOps Platform Knowledge — OpenShift AI and Cloudera CDP/CML
## A complete study document for the Banque Misr retail banking ML programme

This is not a reading list. It is the knowledge itself, organised so that you can learn it
in sequence, plus a time-boxed schedule and verified external resources for depth.

**How to use this document:** Read Part 0 through Part 3 in order — that is the knowledge.
Part 4 is the schedule that makes it fit around a working week. Part 5 is where to go deeper.
Part 6 is how to convert this into visible standing on the team.

**Total time to working competence:** approximately 28 hours, spread over 4 weeks at
1 hour per weekday plus one longer weekend session.

---

# Part 0 — Foundations You Cannot Skip

Both platforms run on Kubernetes. Every capability, limitation, and failure mode in both
products traces back to Kubernetes behaviour. Understanding these six concepts explains
most of what otherwise looks like arbitrary platform behaviour.

## 0.1 Container

A container is a process running with its own isolated filesystem, network namespace, and
resource limits. It is not a virtual machine — there is no separate operating system kernel.
The container shares the host kernel and is isolated by kernel features (namespaces, cgroups).

Why this matters to you: when a pipeline component "cannot import from src," it is because
the container running that component has its own filesystem that does not include your local
project directory. That is the entire explanation for the Dockerfile in this repository.

## 0.2 Pod

A pod is one or more containers scheduled together on the same node, sharing a network
namespace and storage volumes. Kubernetes schedules pods, not containers.

Why this matters: a workbench is a pod. A pipeline step is a pod. A model server is a pod.
When you hear "resources are exhausted," it means the scheduler cannot find a node with
enough free CPU and memory to place a new pod.

## 0.3 Namespace

A namespace is a logical partition of a cluster. Resources in one namespace do not see
resources in another by default. Access control (RBAC) and resource limits (ResourceQuota)
are applied per namespace.

Why this matters: in RHOAI, a **Data Science Project is a namespace**. That single fact
explains RHOAI's isolation model. Team A's project cannot consume Team B's quota because
they are different namespaces with different quotas.

## 0.4 ResourceQuota and LimitRange

**ResourceQuota** caps the total resources a namespace may consume — for example, 32 CPU
and 128 GB RAM across all pods in that namespace combined.

**LimitRange** sets defaults and maximums for individual pods within the namespace — for
example, no single pod may request more than 8 CPU.

Together they are how a platform engineer prevents one team from starving another.

Requests versus limits, which trips everyone up:
- **Request** = what the scheduler reserves. Guaranteed to the pod.
- **Limit** = the ceiling. The pod may burst up to this if the node has spare capacity.

A pod exceeding its memory limit is killed (OOMKilled). A pod exceeding its CPU limit is
throttled, not killed. This distinction matters when debugging why a training job died.

## 0.5 Operator

An operator is a controller that extends Kubernetes with custom resources and the logic to
manage them. You declare a desired state; the operator reconciles reality toward it.

Why this matters: RHOAI *is* an operator. Installing RHOAI means installing an operator that
then manages custom resources like `DataScienceCluster` and `DataSciencePipelinesApplication`.
When you run `oc get dspa`, you are querying a custom resource that the RHOAI operator owns.

## 0.6 PersistentVolumeClaim (PVC)

A PVC is a request for storage that outlives the pod. Without a PVC, everything written
inside a container disappears when the pod stops.

Why this matters: a workbench needs a PVC or your notebooks vanish on restart. Object
storage (MinIO/S3) is a different thing — it is accessed over the network by API, not
mounted as a filesystem.

**Checkpoint for Part 0:** You should be able to explain, without notes, why a Data Science
Project in RHOAI provides resource isolation and a CML workspace does not.

---

# Part 1 — Red Hat OpenShift AI

## 1.1 What RHOAI actually is

RHOAI is a set of Kubernetes operators that install a curated MLOps stack onto an existing
OpenShift cluster. It is not a separate platform — it adds AI/ML capability to infrastructure
you already run. It was previously named Red Hat OpenShift Data Science (RHODS); documentation
older than 2023 uses that name.

The underlying upstream project is **Open Data Hub**. RHOAI is the supported, hardened
downstream distribution of it. Every component is open source.

## 1.2 The components, and what each one is for

### Data Science Project
A Data Science Project is an OpenShift namespace with RHOAI metadata attached. It is the unit
of organisation, access control, and resource quota. Everything else lives inside one.

### Workbench
A containerised development environment — in practice, JupyterLab running as a pod.

Key properties you configure:
- **Notebook image**: which runtime (standard data science, PyTorch, TensorFlow, Spark,
  or a custom image you build)
- **Deployment size**: a named resource profile (Small = 1 CPU / 8 GB, Medium = 3 CPU / 24 GB,
  and so on — these are configurable by the cluster admin)
- **Persistent storage**: a PVC, so your work survives a restart
- **Data connections**: S3 credentials injected as environment variables
- **Git repository**: the workbench can be created from a repo URL

The workbench ships with the JupyterLab Git extension — branch, commit, diff, and merge from
the UI. This is a meaningful practical difference from CML, where Cloudera's own documentation
directs you to use `git` from the terminal.

Critical operational point: **a stopped workbench releases its CPU and memory back to the
cluster.** The PVC persists; the compute does not. This is the mechanism behind RHOAI's
resource efficiency.

### Data Connection
A stored set of S3-compatible credentials (endpoint, access key, secret key, bucket) that
RHOAI injects into workbenches and pipeline pods as environment variables. This is why your
code reads `os.getenv("AWS_ACCESS_KEY_ID")` rather than hardcoding anything.

### Data Science Pipelines (DSPA)
RHOAI's managed **Kubeflow Pipelines v2** installation. `DataSciencePipelinesApplication` is
the custom resource; `oc get dspa -n <namespace>` tells you whether it exists.

A pipeline is a directed acyclic graph of containerised steps. You write it in Python using
the KFP SDK, compile it to YAML (an Argo Workflow specification), and submit it.

The KFP v2 mental model:
- A **component** is a Python function with typed inputs and outputs, executed in a container
- An **artifact** is a typed output (`Dataset`, `Model`, `Metrics`) tracked with lineage
- A **pipeline** wires components together; data dependencies define execution order
- `task_b.after(task_a)` forces ordering when there is no data dependency

The single most common failure: a component importing a local module that is not in the
container image. Solutions are (a) `packages_to_install` for PyPI packages, or (b) a custom
base image with your package baked in — which is what this repository does via its Dockerfile.

### MLflow
Experiment tracking. Three things to know:

- **Parameters** — inputs you set (learning rate, number of records, suite name). Logged once.
- **Metrics** — measured outputs (accuracy, validation success percentage). Can be logged
  repeatedly over steps.
- **Artifacts** — files (HTML reports, JSON results, serialised models). Stored in the
  artifact store, which is S3/MinIO.

For a data preparation pipeline, MLflow gives you the audit history: for any run on any date,
what the data quality was, what the class balance was, and where the output landed.

### Model Serving — KServe and ModelMesh
Two runtimes for two different shapes of problem:

- **KServe** — one model per deployment, scales independently, supports scale-to-zero.
  Use for large models and for anything needing GPU. This is where vLLM plugs in for LLMs.
- **ModelMesh** — many models sharing a serving pod, loaded and unloaded on demand.
  Use when you have dozens or hundreds of small models and per-model pods would be wasteful.

For retail banking: a fraud model serving real-time inference is a KServe workload.

### Model Registry
Added in RHOAI 2.15 (November 2024). Central catalogue of models with versions, metadata,
and deployment state. Before 2.15 you needed external tooling — which is why evaluations of
RHOAI conducted before late 2024 understate its maturity.

### TrustyAI
Also added at 2.15. Two capabilities:

- **Data drift detection** — compares the distribution of live inference inputs against the
  training data distribution. Flags when they diverge. Essential because a fraud model
  trained on pre-inflation transaction amounts degrades as amounts shift.
- **Bias detection** — measures whether model outcomes differ unfairly across protected
  attributes. Metrics include statistical parity difference and disparate impact ratio.

Bias detection has **no native equivalent in CML**. For retail credit risk scoring, being
able to evidence that a model does not discriminate is increasingly a regulatory expectation,
not a nice-to-have.

### Distributed Workloads (Ray / CodeFlare)
For training that exceeds a single node. Not needed for data preparation; relevant later when
model training scales.

## 1.3 The RHOAI mental model in one paragraph

You create a Data Science Project, which is a namespace with a resource quota. Inside it you
attach a Data Connection pointing at MinIO. You start a Workbench to develop interactively.
When the logic is proven, you wrap it as KFP components and submit a pipeline to the DSPA
server, which runs each step as a pod, passing typed artifacts between them and logging to
MLflow. Validated outputs land in S3. A trained model is registered in the Model Registry,
served via KServe, and monitored by TrustyAI. Everything is a Kubernetes resource, so
everything is auditable through the OpenShift API and controllable through RBAC.

**Checkpoint for Part 1:** Draw the flow from workbench through pipeline to served model
from memory, naming the component responsible at each stage.

---

# Part 2 — Cloudera Data Platform and Cloudera AI (CML)

You need this knowledge for two reasons: the bank runs it, and you cannot credibly argue a
platform position without understanding what you are comparing against.

## 2.1 What CDP actually is

Cloudera Data Platform is an integrated data platform. CML — renamed **Cloudera AI** in 2026,
though the CML name remains in most documentation and everyday use — is one service within it.

This is the single most important structural fact: **CML alone is a fraction of what Cloudera
sells.** Its value proposition depends on the surrounding services.

### The CDP services

**CDW — Cloudera Data Warehouse.** SQL analytics using Hive and Impala over an open lakehouse,
increasingly on Apache Iceberg table format. This is where curated banking tables live.

**CDE — Cloudera Data Engineering.** Managed Apache Spark with Apache Airflow orchestration.
This is the heavy ETL layer. Airflow DAGs orchestrate Spark jobs, and a CML operator lets
Airflow trigger CML jobs too.

**CDF — Cloudera DataFlow.** Streaming ingestion using Apache NiFi and Kafka. Real-time
transaction feeds land here.

**SDX — Shared Data Experience.** The governance layer, and Cloudera's strongest asset:
- **Apache Ranger** — policy-based access control down to the column level. "This user may
  read `annual_income` but not `national_id` in the customer table." Enforced at the data
  layer, so it holds regardless of which tool is querying.
- **Apache Atlas** — metadata catalogue and automated lineage. Records where data came from,
  how it was transformed, who accessed it, and which models consumed it.

**Cloudera Manager.** Cluster administration and monitoring.

### Where CML sits

CML runs on Kubernetes — specifically on Red Hat OpenShift Container Platform or on Cloudera's
own Embedded Container Service. It provides ML workspaces with governed access to CDP data.

## 2.2 CML concepts

### Workspace
The top-level container for teams and projects. This is the resource allocation boundary,
and understanding it explains most of the bank's capacity concerns.

Documented minimum footprint per workspace: 128 GB RAM (256 GB recommended), 32 CPU cores
(32–48 recommended), 4 TB block storage, 1 TB NFS.

Cloudera's own sizing guidance recommends deploying **multiple workspaces** segmented by use
case, team, and function — which is how you achieve isolation in CML, and which multiplies
that footprint for every isolation boundary you need.

### Project
A workspace contains projects. A project is a filesystem at `/home/cdsw` plus its git
configuration and settings. Files persist across sessions. Projects can be created from a
Git URL.

Important characteristic: Cloudera's documentation states CML "does not include significant
UI support for Git, but instead allows you to use the full power of the command line," and
recommends each team member create a *separate* project from the central repository.

### Session
An interactive compute environment — the equivalent of an RHOAI workbench. A session runs a
chosen ML Runtime with a chosen resource profile.

### ML Runtime
The container image for a session. Bundles editor, kernel, Python version, and libraries.
Versioned by date (2024.02.1, 2025.01.1, and so on).

Changes you must be aware of in 2025.01.1:
- The `cdsw` Python module was **replaced** by the `cml` module — a breaking change for any
  existing code that uses it
- JupyterLab migrated to PBJ (Powered by Jupyter)
- Workbench-based Python images were **removed**
- Python 3.7 and 3.8 images are **no longer supported**
- Only the Python 3.7 runtime is compatible with Spark 2 — so Spark 2 workloads are stuck on
  an unsupported Python

Also: **Cloudera Data Science Workbench (CDSW) reached end of support in May 2024.**

### Job
A script executed on a schedule or trigger. Jobs can be chained into dependency pipelines and
are the mechanism for automated retraining. For complex DAGs, Airflow in CDE is the stronger tool.

### Experiment
Versioned, reproducible training runs. Recent versions integrate MLflow.

### Model
Deploy a Python function as a REST endpoint in a few clicks. Genuinely simple, and a real
strength for data scientists who do not want to think about serving infrastructure.

### Application
A long-running web application — Flask, Streamlit, Shiny — served from within CML. Useful
for delivering dashboards to business users. RHOAI has no direct equivalent.

### AMPs — Applied Machine Learning Prototypes
Over 130 one-click deployable end-to-end ML projects. Genuinely valuable for rapid
prototyping and for learning patterns. RHOAI has no equivalent.
Catalogue: https://cloudera.github.io/Applied-ML-Prototypes/

### Spark on Kubernetes
CML spins Spark clusters up and down on demand from within a session, with direct governed
access to CDP data. This is Cloudera's clearest technical advantage over RHOAI.

## 2.3 Known issues you should be able to cite

From Cloudera's own published release notes:

- **TSB 2025-844** — garbage collection for pods in `Error` and `Init:Unknown` states is not
  occurring in certain versions. Cloudera states this "can prevent the deployment of new pods
  and lead to unnecessary cloud costs for stale workload pods." This is directly relevant to
  any "workspace is full" symptom.
- **TSB 2025-826** — non-authorised but authenticated users can perform create, update, and
  delete operations on Cloudera AI Registry metadata tables including models, model versions,
  and tags.
- Cloudera AI Registry is not supported for R models.
- `mlflow.log_model` registered files may not reach the NFS server due to NFS or network
  settings, leaving a model stuck in registering state.
- The web pod crashes if a project fork exceeds 60 minutes.

Knowing these by name, with the TSB numbers, is the difference between opinion and analysis
in a stakeholder meeting.

**Checkpoint for Part 2:** Explain the difference between a CML workspace and a CML project,
and why the workspace boundary is where the capacity constraint originates.

---

# Part 3 — Concept Translation Map

Learning the mapping halves the effort of learning the second platform.

| Concept | RHOAI | Cloudera AI (CML) |
|---|---|---|
| Isolation boundary | Data Science Project (namespace) | Workspace |
| Resource control | ResourceQuota / LimitRange | Workspace allocation + resource profile |
| Interactive environment | Workbench | Session |
| Container image | Notebook image (ImageStream) | ML Runtime |
| Code organisation | Git repo cloned into workbench | Project at `/home/cdsw` |
| Pipeline orchestration | Kubeflow Pipelines v2 | Jobs; Airflow in CDE |
| Experiment tracking | MLflow | Experiments (MLflow-backed) |
| Model registry | Model Registry (2.15+) | Cloudera AI Registry |
| Model serving | KServe / ModelMesh | Models |
| Drift monitoring | TrustyAI | Model Metrics + Evidently.ai AMP |
| Bias monitoring | TrustyAI | No native equivalent |
| Object storage | MinIO / ODF (S3) | S3 / ADLS / HDFS |
| Data access control | OpenShift RBAC (namespace) | Apache Ranger (column level) |
| Lineage and audit | OpenShift audit log; MLflow | Apache Atlas (automated) |
| Distributed Spark | Spark Operator (manual setup) | Native Spark-on-K8s |
| Web app hosting | Not native | Applications |
| Project templates | Not native | AMPs (130+) |

**The two asymmetries that matter most:**

Cloudera has Ranger column-level access control and Atlas automated lineage. RHOAI has
neither. This is a *data layer* capability, which is why the recommended architecture keeps
CDP as the data layer.

RHOAI has TrustyAI bias detection. Cloudera has no native equivalent. For credit risk models
under regulatory scrutiny, this matters.

---

# Part 4 — Four-Week Schedule

Designed for approximately 1 hour per weekday plus a longer weekend session. Every week ends
with something you can show the team.

## Week 1 — Foundations and RHOAI core

| Day | Time | Activity |
|---|---|---|
| Mon | 60 min | Part 0 of this document. Then in a terminal: `oc get namespace`, `oc get resourcequota -n <ns>`, `oc describe node`. Connect the concepts to real output. |
| Tue | 60 min | Part 1.1–1.2 up to Data Connections. Create a Data Science Project and a workbench in the RHOAI dashboard. Stop it. Watch the resources return. |
| Wed | 60 min | KFP v2 concepts. Read `src/pipeline/components.py` in this repository line by line. Identify every input, output, and artifact type. |
| Thu | 60 min | Compile the pipeline: `make compile-pipeline`. Open the generated YAML. Find where your Python became an Argo Workflow spec. |
| Fri | 60 min | MLflow: parameters versus metrics versus artifacts. Map each to what our Great Expectations validation logs. |
| Weekend | 3 hrs | Red Hat "From raw data to model serving with OpenShift AI" — a complete fraud detection MLOps walkthrough, directly relevant to our use case. Link in Part 5. |

**Week 1 output:** You can explain the full RHOAI pipeline flow at a whiteboard without notes.

## Week 2 — RHOAI depth and our own pipeline

| Day | Time | Activity |
|---|---|---|
| Mon | 60 min | Model serving: KServe versus ModelMesh. When each applies. Read RHOAI serving documentation. |
| Tue | 60 min | TrustyAI: drift metrics and bias metrics. Which fairness metric would apply to our credit risk model, and why. |
| Wed | 60 min | Run `scripts/verify_rhoai_env.sh` against the cluster. Document every result. |
| Thu | 60 min | Build the pipeline image: `make build-image`. Understand exactly what the Dockerfile solves. |
| Fri | 60 min | Great Expectations: read `src/validation/expectation_suites.py`. Add two new expectations relevant to retail banking. |
| Weekend | 3 hrs | Free Red Hat introductory AI courses (Part 5). Then run our full pipeline locally end to end. |

**Week 2 output:** Environment verification results documented and shared with the platform team.

## Week 3 — Cloudera CDP and CML

| Day | Time | Activity |
|---|---|---|
| Mon | 60 min | Part 2.1 of this document. Then the free "Cloudera Essentials for CDP" course. |
| Tue | 60 min | Free "Introduction to Cloudera Machine Learning" course (approximately 1 hour). |
| Wed | 60 min | Part 2.2. In our CML instance: identify the workspace, list projects, check the ML Runtime version. |
| Thu | 60 min | Part 2.3. Read the Cloudera known issues page. Check our version against TSB 2025-844 and TSB 2025-826. |
| Fri | 60 min | Ranger and Atlas. What policies exist today? Is Atlas lineage populated for ML workloads? |
| Weekend | 3 hrs | Deploy one AMP in CML and read its code. Understand how Cloudera structures an end-to-end project. |

**Week 3 output:** Answers to the seven Open Questions in the platform analysis document.

## Week 4 — Synthesis and positioning

| Day | Time | Activity |
|---|---|---|
| Mon | 60 min | Part 3 translation map. Reproduce it from memory. |
| Tue | 60 min | Test CDW connectivity from an RHOAI workbench via JDBC. Verify Ranger enforcement. |
| Wed | 60 min | Draft the coexistence architecture with our actual service names and endpoints. |
| Thu | 60 min | Define the five KPIs for a 90-day parallel evaluation. Make them measurable. |
| Fri | 60 min | Rehearse the platform recommendation. Ten minutes, evidence-led, no advocacy. |
| Weekend | 3 hrs | Begin AI267 course material if a Red Hat Learning Subscription is available. |

**Week 4 output:** An evidence-based platform recommendation you can defend to any stakeholder.

---

# Part 5 — Verified External Resources

All links below were verified as live. Free resources are marked.

## Red Hat OpenShift AI

**Start here — free, and directly relevant to our fraud use case:**
- From raw data to model serving with OpenShift AI (complete fraud detection MLOps walkthrough):
  https://developers.redhat.com/articles/2025/07/29/raw-data-model-serving-openshift-ai

**Free documentation and learning:**
- Red Hat AI learning hub — hands-on guides for training, deploying, and refining models:
  https://docs.redhat.com/en/learn/ai
- AI on OpenShift — community site, practical patterns and tooling:
  https://ai-on-openshift.io/
- RHOAI getting started: https://ai-on-openshift.io/getting-started/openshift-ai/
- Red Hat Developer RHOAI product hub: https://developers.redhat.com/products/red-hat-openshift-ai
- Free on-demand introductory courses (RHEL, OpenShift, AI):
  https://www.redhat.com/en/engage/demand-free-introductory-courses-0
- Red Hat Hybrid Cloud learning hub: https://cloud.redhat.com/learn

**Official documentation:**
- OpenShift AI product page: https://www.redhat.com/en/products/ai/openshift-ai
- Customer portal documentation: https://access.redhat.com/products/red-hat-openshift-ai/
- TrustyAI monitoring (drift and bias):
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/monitoring_your_ai_systems/index

**Paid training and certification — the strongest career signal:**
- **AI267 — Developing and Deploying AI/ML Applications on Red Hat OpenShift AI**
  https://www.redhat.com/en/services/training/ai267-developing-and-deploying-ai/ml-applications-on-red-hat-openshift-ai
  Covers RHOAI architecture, workbenches, model serving, bias and drift monitoring, and
  data science pipelines. Prerequisites are Python experience and OpenShift familiarity.
- **EX267 — Red Hat Certified Specialist in OpenShift AI** — the performance-based exam
  associated with AI267. This is the credential to target.
- Coursera hosts a Red Hat Training course, "Introduction to Red Hat OpenShift AI"
  (approximately 4 hours, intermediate, certificate available). Search Coursera for the title.

**Video:** Red Hat's official YouTube channel carries OpenShift AI demonstration and
architecture sessions. Search the channel for "OpenShift AI" and "TrustyAI". Prefer the
official channel over third-party uploads, since RHOAI has changed substantially since 2.15
and older third-party material is misleading.

## Cloudera CDP and CML

**Free — over 20 courses in the OnDemand library are available at no cost:**
- Cloudera OnDemand catalogue: https://ondemand.cloudera.com/courses
- Cloudera Education platform: https://education.cloudera.com
- Cloudera Essentials for CDP (approximately 4 hours, conceptual, no technical prerequisites):
  https://www.cloudera.com/services-and-support/training/courses/cloudera-essentials-for-cdp.html
- Introduction to Cloudera Machine Learning (approximately 1 hour):
  https://www.cloudera.com/services-and-support/training/courses/cdp-intro-to-cloudera-machine-learning.html

Other free courses in the catalogue relevant to us: Introducing Cloudera Data Engineering
(Spark applications), Introduction to Cloudera Data Warehouse, CDP Building AI Applications
with CML, and Apache Kafka Basics.

**Learning path and certification:**
- Cloudera ML Engineer learning path — includes an exam testing ML engineering skills on CDP:
  https://www.cloudera.com/services-and-support/training/learning-paths/ml-engineer.html

**Official documentation — read these two properly:**
- Cloudera AI overview:
  https://docs.cloudera.com/machine-learning/cloud/product/topics/ml-product-overview.html
- Known issues and limitations (this is where the TSB advisories live):
  https://docs.cloudera.com/machine-learning/cloud/release-notes/topics/ml-known-issues-limitations.html

**Hands-on:**
- Applied ML Prototypes catalogue: https://cloudera.github.io/Applied-ML-Prototypes/
- Continuous model monitoring AMP (drift detection with Evidently.ai):
  https://github.com/cloudera/CML_AMP_Continuous_Model_Monitoring
- Machine Learning Ops with Cloudera AI (community article):
  https://community.cloudera.com/t5/Community-Articles/Machine-Learning-Ops-with-Cloudera-AI/ta-p/403841

## Underlying technologies

- Kubeflow Pipelines v2 SDK documentation — the KFP concepts underpinning RHOAI pipelines
- Great Expectations documentation — expectation suites and data contracts
- MLflow documentation — tracking, registry, and artifact management
- Apache Ranger and Apache Atlas documentation — the governance model behind SDX

---

# Part 6 — How This Makes You Stand Out

Knowledge alone does not change how a team sees you. These five behaviours convert it into
standing, and each one is achievable within the four weeks above.

**1. Cite advisories by number.** When the capacity question comes up, "TSB 2025-844 describes
a pod garbage collection defect that produces exactly this symptom — I would like to check our
version before we conclude we are out of capacity" is a different order of contribution than
"maybe we need more resources." You now have those numbers.

**2. Bring the asymmetries, not a scorecard.** Anyone can produce a feature comparison table.
The valuable observation is that Cloudera's advantage (Ranger, Atlas) is at the *data* layer
and RHOAI's advantage (TrustyAI bias detection, namespace isolation) is at the *ML* layer —
which is precisely why coexistence beats replacement. That reframing is the contribution.

**3. Answer the question nobody asked.** "Which CDP services do we actually use in production
beyond CML?" determines whether the Cloudera licence is good value or poor value. If nobody
has asked it, asking it is leadership.

**4. Make everything reproducible.** The repository is the differentiator. Anyone can present
slides. `git clone` and `make generate-data` producing 500,000 records in ten seconds is
evidence. Keep that bar.

**5. Be honest about what your own analysis weakens.** TSB 2025-844 cuts against the migration
argument as much as it cuts against Cloudera. Saying so out loud is what makes the rest of
your analysis credible. Advocacy is discounted; evidence is not.

**Certification target:** EX267, Red Hat Certified Specialist in OpenShift AI. It is
performance-based rather than multiple choice, it maps directly to the platform you are
implementing, and there is currently no equivalent depth of RHOAI credential on the team.

---

# Appendix — Self-Assessment

Work through these without notes. Gaps show you what to revisit.

**Foundations**
1. Why does a stopped RHOAI workbench free cluster resources while a CML workspace allocation
   does not?
2. What is the practical difference between a resource request and a resource limit, and what
   happens when each is exceeded?
3. Why can a KFP component not import a module from your local project directory?

**OpenShift AI**
4. Name the five phases of our data preparation pipeline and the tool used at each.
5. When would you choose KServe over ModelMesh?
6. Which TrustyAI capability has no equivalent in Cloudera, and why does it matter for credit risk?
7. What does `oc get dspa -n <namespace>` tell you, and what does an empty result mean?

**Cloudera**
8. What is the difference between a CML workspace and a CML project?
9. Which CDP service provides column-level access control, and which provides lineage?
10. What breaking change did ML Runtimes 2025.01.1 introduce for existing code?
11. What does TSB 2025-844 describe, and why is it relevant to our capacity discussion?

**Synthesis**
12. Which parts of CML can RHOAI replace, and which parts can it not?
13. Why is coexistence the recommended architecture rather than migration?
14. What single test would determine whether the coexistence architecture is viable?
