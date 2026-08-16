# Cloudera (CDP/CML) vs Red Hat OpenShift AI
## Platform Analysis for Banque Misr Retail Banking ML Programme

**Prepared by:** MLOps Engineering
**Scope:** Retail banking ML use cases — fraud/AML detection, credit risk scoring, customer churn
**Question addressed:** Can Red Hat OpenShift AI replace Cloudera Machine Learning given that
Banque Misr already runs CML and the wider Cloudera Data Platform?

---

## Executive Summary

**Short answer: partially, and replacement is the wrong framing.**

Red Hat OpenShift AI (RHOAI) can replace the CML *workspace and MLOps layer* — notebooks,
pipelines, experiment tracking, model serving. It cannot replace the Cloudera Data Platform
*data layer* — Hive Metastore, Cloudera Data Warehouse, Apache Ranger policy enforcement,
Apache Atlas lineage. Those are data infrastructure, not ML tooling, and RHOAI has no
equivalent.

The realistic architecture is **coexistence, not replacement**: retain CDP as the governed
data platform, adopt RHOAI as the ML compute and MLOps layer, and connect the two. This
preserves the bank's governance investment while resolving the documented capacity and
tooling constraints in CML.

Three findings below materially change the debate. Two of them come from Cloudera's own
published release notes.

---

## Part 1 — Findings Grounded in Our Own Evaluation

During the Cloudera platform evaluation, our team documented nine specific concerns. Each is
addressed below with verified vendor documentation, alongside how RHOAI handles the same
concern. This is the substance of the comparison — these are our observed issues, not
generic feature checklists.

### Concern 1: "Same project → changes untracked"

**Our observation:** Work in a shared Cloudera Workbench project is not version-controlled;
concurrent edits risk being lost or overwritten.

**Verified:** This is a documented product characteristic, not a misconfiguration.
Cloudera's own documentation states that Cloudera Data Science Workbench "does not include
significant UI support for Git, but instead allows you to use the full power of the command
line." Cloudera's guidance is that each team member creates a *separate* project from the
central Git repository, and runs `git` commands manually from a terminal inside the session.

**RHOAI equivalent:** JupyterLab workbenches in RHOAI ship with the JupyterLab Git extension,
providing branch, commit, diff, and merge operations in the UI. Workbenches can be created
directly from a Git repository URL and the clone is a first-class project property.

**Assessment:** Genuine advantage to RHOAI. This concern is resolved rather than worked around.

---

### Concern 2: "Can Cloudera support multi-kernel (many Python versions)?"

**Verified:** CML uses one ML Runtime per session. A runtime bundles a specific Python
version, editor, and library set. Multiple Python versions require multiple runtimes,
selected at session launch — not multiple kernels within one session.

Critically, Cloudera's ML Runtimes 2025.01.1 release notes confirm that **Python 3.7 and
3.8-based images are no longer supported**, and that **only the Python 3.7 runtime is
compatible with Spark 2**. Teams still on Spark 2 are therefore locked to an unsupported
Python version.

**RHOAI equivalent:** Multiple notebook images are available per cluster (standard data
science, PyTorch, TensorFlow, Spark-enabled), selected per workbench. Custom images can be
built and registered as ImageStreams, giving full control over Python version and library set.

**Assessment:** Both platforms use per-session runtimes rather than true multi-kernel.
RHOAI's custom image path is more open. The Spark 2 / Python 3.7 lock-in in CML is a real
migration risk for the bank if any pipelines still depend on Spark 2.

---

### Concern 3: "Are there the latest Spark versions in Cloudera sessions?"

**Verified:** CML supports Spark-on-Kubernetes natively and this remains one of Cloudera's
genuine strengths — Spark clusters spin up and down on demand from within an ML session,
with direct access to CDP data. However, Spark version availability is tied to the ML Runtime
release, and the Spark 2 / Python 3.7 dependency noted above constrains upgrade paths.

**RHOAI equivalent:** No managed Spark cluster service. PySpark runs in workbenches, and
distributed Spark requires deploying the Spark Operator for Kubernetes separately and
invoking it from pipeline steps.

**Assessment:** Clear advantage to Cloudera. If retail fraud or AML processing requires
distributed Spark over hundreds of millions of transactions, this gap is material and
must be planned for, not assumed away.

---

### Concern 4: "Runtime image of Jupyter Notebook — is it the latest? (2024)"

**Verified:** Our note recorded 2024 as the runtime year. Cloudera's ML Runtimes have since
released 2025.01.1, which brought significant changes: the `cdsw` Python module was replaced
by the `cml` module, JupyterLab migrated to PBJ (Powered by Jupyter), Workbench-based Python
images were removed entirely, and Python 3.7/3.8 support was dropped.

If the bank is still on 2024.02.1 runtimes, we are one major runtime generation behind, and
the upgrade involves a breaking API change (`cdsw` → `cml`) in any existing code that uses it.

Note also that **Cloudera Data Science Workbench (CDSW) reached end of support in May 2024**.
Any CDSW-based workflows are unsupported.

**RHOAI equivalent:** Notebook images are versioned ImageStreams updated with each RHOAI
release. Multiple versions can be kept available simultaneously, so teams migrate on their
own schedule rather than at a forced cutover.

**Assessment:** Actionable finding independent of the platform decision. We should confirm
our current runtime version and plan the `cdsw` → `cml` migration regardless of which
platform we standardise on.

---

### Concern 5: "Resource Profile — are the resources sufficient or too little?"

**Verified:** CML allocates resources at the **workspace** level. Documented minimums per
workspace: 128 GB RAM (256 GB recommended), 32 CPU cores (32–48 recommended), 4 TB block
storage, plus 1 TB NFS. Individual sessions then draw from that pool via resource profiles.

**RHOAI equivalent:** Resources are allocated per **workbench session**, governed by
Kubernetes ResourceQuota and LimitRange at the namespace level. A stopped workbench returns
its resources to the cluster immediately.

**Assessment:** Architectural difference with real consequences. CML reserves a large fixed
pool per workspace whether or not it is in use. RHOAI's per-session model means the same
hardware supports more concurrent users. This is the root of the capacity issue — see
Finding A below.

---

### Concern 6: "Do people affect each other's resources? (e.g. Retail heavy model)"

This was the sharpest concern in our evaluation and it has a direct, documented answer.

**Verified:** Yes. Within a CML workspace, sessions share the workspace resource pool. A
resource-heavy retail model training run consumes capacity that other users then cannot
access. Cloudera's own sizing guidance recommends deploying **multiple separate workspaces**
by use case, team, and function specifically to achieve isolation — which multiplies the
128–256 GB per-workspace overhead for every isolation boundary required.

**RHOAI equivalent:** Each data science project is an OpenShift namespace with its own
ResourceQuota. A retail team's workload cannot consume the risk team's quota. Isolation is
enforced by Kubernetes, not by provisioning separate heavyweight workspaces.

**Assessment:** Clear advantage to RHOAI, and directly relevant to us. Our retail models are
the heavy workload. Under CML, isolating them properly means standing up a dedicated
workspace with its own 128 GB+ footprint. Under RHOAI, it means setting a namespace quota.

---

### Concern 7: "Do admins have access to a user activity log (who did what)?"

**Verified:** Yes for CML. Cloudera SDX provides audit through Apache Atlas and Apache Ranger,
covering data access, lineage, and policy enforcement across the whole CDP estate. This is
genuinely strong and is Cloudera's most defensible advantage in a regulated bank.

**However**, Cloudera has published a security advisory relevant to this claim:
**TSB 2025-826** — non-authorised but authenticated users can perform create, update, and
delete operations on Cloudera AI Registry metadata tables, including model, model-version,
and tag records. In a bank where the model registry is part of the model risk management
evidence chain, this warrants verification against our installed version.

**RHOAI equivalent:** OpenShift audit logs capture API-level actions (who created, modified,
or deleted which resource). This is infrastructure-level auditing. RHOAI has **no equivalent
to Ranger's column-level data access control** and **no equivalent to Atlas's automated data
lineage**.

**Assessment:** Cloudera wins on data governance depth. This is the single strongest argument
for retaining CDP, and it is a data-layer capability — which is why the recommendation below
is coexistence rather than replacement.

---

### Concern 8: "Jupyter Notebook vs Workbench (resources wise)"

**Verified:** In current CML, this distinction has largely collapsed. As of ML Runtimes
2025.01.1, JupyterLab has been migrated to PBJ and Workbench-based Python images have been
removed — only PBJ Workbench and JupyterLab runtimes are released going forward. Both consume
resources from the same workspace pool; the difference is editor interface, not resource model.

**Assessment:** Concern is largely resolved by Cloudera's own product direction. No longer
a differentiating factor.

---

### Concern 9: "Validate all facts with Cloudera admins"

This document is that validation, sourced from Cloudera's published documentation and release
notes. Items requiring direct confirmation from our Cloudera administrators are listed in
the Open Questions section at the end.

---

## Part 2 — Three Findings That Change the Decision

### Finding A: The capacity problem may be partly a known Cloudera defect, not a hardware shortage

Cloudera has published **TSB 2025-844**: garbage collection for pods in `Error` and
`Init:Unknown` states inside Cloudera AI Workbenches is not occurring in certain versions.
Cloudera's own description states this "can prevent the deployment of new pods and lead to
unnecessary cloud costs for stale workload pods no longer serving any purpose."

The symptom — new sessions cannot start, the workspace appears fully consumed — matches the
capacity problem described to us precisely.

**Why this matters for the decision:** If a meaningful share of our CML workspace capacity is
being held by orphaned pods, then "CML is fully utilised" may not mean "CML has reached its
useful capacity." It may mean we are running a version with a known resource-leak defect.

**This finding cuts both ways, honestly:**
- It weakens the argument that we must migrate because CML is out of capacity. Patching may
  recover substantial capacity at no licensing cost.
- It also evidences an operational quality concern in a platform we depend on for regulated
  workloads.

**Action:** Before any platform decision, confirm our CML version against TSB 2025-844 and
audit for orphaned pods. This is a one-session check and it may reframe the entire discussion.

---

### Finding B: CML runs *on* OpenShift — this is not an either/or infrastructure choice

Cloudera's documentation confirms CML requires Red Hat OpenShift Container Platform or
Cloudera's Embedded Container Service to run. Red Hat and Cloudera maintain a formal
partnership and jointly publish guidance on running Cloudera AI on OpenShift.

**Implication for Banque Misr:** The bank already operates OpenShift — it has to, in order to
run CML. The question is therefore not "which infrastructure" but "which software layer sits
above the OpenShift we already pay for."

This materially changes the cost comparison. RHOAI is delivered as an operator on OpenShift.
Cloudera CDP licensing is a separate and substantial commercial line item — published
enterprise pricing indicates figures in the range of £97,776 per year for a 100 TB platform,
with public cloud consumption pricing from $0.07 per Cloudera Compute Unit per hour.

**Action:** Procurement should confirm whether RHOAI is already entitled under our existing
Red Hat OpenShift subscription, and what portion of the Cloudera spend is attributable to the
CML service specifically versus the CDW/CDE/CDF data services.

---

### Finding C: RHOAI closed its three biggest capability gaps in November 2024

RHOAI 2.15, released 12 November 2024, added:

- **Model Registry** — centralised model catalogue with versioning and deployment state
- **Data drift detection (TrustyAI)** — monitors deployed models for divergence between
  production inference data and training data distribution
- **Bias detection (TrustyAI)** — monitors deployed models for unfair outcomes across
  protected attributes

The bias detection capability has no native equivalent in CML. For retail credit risk scoring
in particular, demonstrating that a model does not discriminate on protected characteristics
is an increasingly explicit regulatory expectation. This is a capability RHOAI has and
Cloudera does not.

Any prior evaluation of RHOAI conducted before late 2024 is out of date on these three points.

---

## Part 3 — Direct Answer: Can RHOAI Replace CML?

Broken down by layer, because the answer differs by layer.

| Layer | Currently provided by | Can RHOAI replace it? | Notes |
|---|---|---|---|
| Notebook / IDE workspace | CML Sessions | Yes | RHOAI workbenches, with better Git UI support |
| Pipeline orchestration | CML Jobs / CDE Airflow | Partially | KFP v2 covers ML pipelines; Airflow is stronger for complex data engineering DAGs |
| Experiment tracking | CML Experiments | Yes | MLflow, integrated |
| Model registry | Cloudera AI Registry | Yes | RHOAI Model Registry (since 2.15) |
| Model serving | CML Models | Yes | KServe and ModelMesh; vLLM for GenAI |
| Drift monitoring | CML Model Metrics | Yes | TrustyAI |
| Bias / fairness monitoring | Not available natively | Yes — new capability | TrustyAI |
| Distributed Spark | Native Spark-on-K8s | **No** | Requires separate Spark Operator deployment |
| Data warehouse / SQL | CDW (Hive, Impala) | **No** | Not an ML platform function |
| Column-level access control | Apache Ranger (SDX) | **No** | No RHOAI equivalent |
| Automated data lineage | Apache Atlas (SDX) | **No** | No RHOAI equivalent |
| Data streaming | CDF (NiFi, Kafka) | **No** | Not an ML platform function |
| One-click ML templates | AMPs (130+) | **No** | No RHOAI equivalent |

**Conclusion:** RHOAI can replace the CML service. RHOAI cannot replace the Cloudera Data
Platform. If the bank uses CDW, CDE, CDF, and SDX governance in production, those remain
regardless of the ML platform decision.

---

## Part 4 — Recommended Architecture: Coexistence

The strongest technical position for Banque Misr is not migration and not status quo. It is
a deliberate separation of concerns:

```
┌──────────────────────────────────────────────────────────────┐
│  Cloudera Data Platform — GOVERNED DATA LAYER                │
│                                                              │
│  CDW (Hive / Impala / Iceberg)   Curated retail banking data │
│  Apache Ranger                    Column-level access control │
│  Apache Atlas                     Lineage and audit trail     │
│  CDE (Spark / Airflow)            Heavy distributed ETL       │
└──────────────────────────────────────────────────────────────┘
                              │
                   JDBC / Iceberg REST Catalog
                   (Ranger policies still enforced)
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Red Hat OpenShift AI — ML COMPUTE AND MLOPS LAYER           │
│                                                              │
│  Workbenches          Per-session resource profiles          │
│  Kubeflow Pipelines   Reproducible, versioned ML pipelines   │
│  MinIO / S3           Feature store and pipeline artifacts   │
│  MLflow               Experiment tracking                     │
│  Great Expectations   Data quality contracts                  │
│  KServe               Model serving                           │
│  TrustyAI             Drift and bias monitoring               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
              Retail models: fraud/AML · credit risk · churn
```

**What this preserves:** Ranger column-level controls and Atlas lineage continue to govern
the data. Nothing in the bank's compliance posture is weakened — data access still flows
through the governed layer.

**What this resolves:** Per-namespace resource isolation for the heavy retail workloads.
Git-native version control. Current runtime images. Bias monitoring for credit risk models.
Reduced dependence on a single ML vendor.

**What this requires:** Configuring RHOAI workbench connectivity to CDW via JDBC or the
Iceberg REST catalog, with Ranger policy enforcement verified end to end. This is the primary
technical unknown and should be the first task of the next sprint.

**What stays on Cloudera:** Any workload requiring native distributed Spark at scale. If
retail fraud feature engineering over the full transaction history needs Spark, that job runs
in CDE and writes its output to a location RHOAI reads from.

---

## Part 5 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| RHOAI cannot enforce Ranger policies on CDW reads | Medium | High | Validate JDBC + Ranger enforcement in a controlled test before committing |
| Distributed Spark gap blocks a retail use case | Medium | High | Keep heavy Spark ETL in CDE; RHOAI consumes the output |
| Loss of Atlas lineage for RHOAI-trained models | High | Medium | Log dataset URIs and versions in MLflow; export to Atlas via API if required |
| CML capacity issue is TSB 2025-844, not real exhaustion | Medium | Medium | Verify version and audit orphaned pods before deciding |
| Runtime migration `cdsw` → `cml` breaks existing code | High | Medium | Inventory code using the `cdsw` module; plan migration regardless of platform choice |
| Cloudera AI Registry RBAC issue (TSB 2025-826) | Unknown | High | Confirm installed version against the advisory |
| Team lacks RHOAI operational depth | High | Medium | Structured curriculum — see docs/learning/ |

---

## Part 6 — Open Questions for Cloudera Administrators

These require direct confirmation and cannot be resolved from documentation:

1. What is our installed CML/Cloudera AI version, and is it affected by TSB 2025-844
   (pod garbage collection) or TSB 2025-826 (registry RBAC)?
2. How many CML workspaces exist, and what is the actual allocated versus consumed
   CPU and RAM per workspace?
3. Which CDP services are in production use beyond CML — CDW, CDE, CDF?
4. Is Apache Ranger actively enforcing column-level policies today, or is access control
   currently at table or schema level?
5. Is Apache Atlas lineage actively populated for ML workloads specifically?
6. What ML Runtime version are we on, and is any code still dependent on the `cdsw` module
   or on Spark 2?
7. What proportion of the Cloudera licence cost is attributable to the CML service?

---

## Part 7 — Recommended Next Actions

1. **Verify the capacity root cause.** Check our CML version against TSB 2025-844 and audit
   for orphaned pods. One session. May recover capacity without any platform change.

2. **Establish licence position.** Confirm with procurement whether RHOAI is entitled under
   the existing OpenShift subscription, and isolate the CML-attributable portion of Cloudera spend.

3. **Complete the RHOAI data preparation POC.** The pipeline is built and validated locally.
   Running it on cluster produces measured evidence rather than argument.

4. **Prove CDW connectivity from RHOAI.** Test JDBC access to a governed CDW table from an
   RHOAI workbench and confirm Ranger policies are enforced. This single test determines
   whether the coexistence architecture is viable.

5. **Run a bounded parallel evaluation.** Ninety days, both platforms, defined criteria:
   pipeline execution time, resource consumption per concurrent user, governance coverage,
   time from data to trained model, and user adoption. Decide on evidence.

---

## Sources

- Cloudera documentation — CML known issues and limitations, including TSB 2025-844 and
  TSB 2025-826 (docs.cloudera.com/machine-learning/cloud/release-notes)
- Cloudera documentation — ML Runtimes 2025.01.1 release notes (`cdsw` → `cml` module change,
  Python 3.7/3.8 removal, Spark 2 constraint, CDSW end of support May 2024)
- Cloudera documentation — Using Git to collaborate on projects (no significant UI support for Git)
- Cloudera Community — Sizing CML workspaces guidance (multiple workspaces for isolation)
- Cloudera pricing documentation and published enterprise pricing schedules
- Red Hat press release — OpenShift AI 2.15, 12 November 2024 (model registry, drift, bias detection)
- Red Hat documentation — TrustyAI drift and bias monitoring, OpenShift AI self-managed
- Red Hat blog — Cloudera AI on Red Hat OpenShift, November 2025
- Red Hat blog — Digital sovereignty for banks, December 2025
- InfoWorld — RHOAI model registry and drift detection coverage, November 2024
- Banque Misr internal Cloudera platform evaluation notes (nine documented concerns)
