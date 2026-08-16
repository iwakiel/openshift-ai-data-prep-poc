# Platform Analysis: Cloudera AI vs Red Hat OpenShift AI
# For: Management and Stakeholders | Retail Banking ML Platform Decision
# Author: MLOps Engineering | Sprint 1 Research

---

## Executive Summary

This analysis compares Cloudera AI (formerly Cloudera Machine Learning, CML) and Red Hat
OpenShift AI (RHOAI) as the ML platform for the bank's retail banking machine learning
programme. The comparison is based on current vendor documentation, independent technical
research, known issues reported in Cloudera's own release notes, and published case studies.

**The critical finding that changes the framing of this debate:**
Cloudera AI runs on Red Hat OpenShift as its underlying infrastructure. These are not
competing infrastructure stacks — the question is what software layer sits above OpenShift.
If the bank already holds an OpenShift subscription, RHOAI may be available at significantly
lower additional cost than the full Cloudera CDP licensing.

**Bottom line:** Neither platform is universally superior. The right choice depends on
whether the bank uses the full Cloudera ecosystem or only CML in isolation, and on
the cost structure of existing licensing.

---

## Key Findings

### Finding 1: CML and RHOAI are not independent platforms — they share the same infrastructure

Cloudera's official documentation confirms that CML requires either Red Hat OpenShift Container
Platform (OCP) or Cloudera's own ECS to run. Red Hat and Cloudera have a formal technology
partnership and co-published integration guidance as recently as November 2025.

The practical implication: the bank is not choosing between two competing infrastructure
approaches. It is choosing between deploying the Cloudera AI software stack on OpenShift
(with full Cloudera licensing costs) versus deploying Red Hat's native AI operator on
the same OpenShift cluster (potentially included in the existing Red Hat subscription).

---

### Finding 2: Cloudera AI's primary advantage is its integrated data ecosystem, not CML alone

CML by itself is an ML workspace. Its real differentiation comes from being part of the
Cloudera Data Platform (CDP), which includes:

- Apache Ranger (column-level data access control across all data services)
- Apache Atlas (automated data lineage and audit trail across the entire data lifecycle)
- Cloudera Data Engineering with Apache Airflow (Spark pipeline orchestration)
- Native Spark-on-Kubernetes (spin up distributed Spark clusters from ML sessions)
- Applied ML Prototypes (130+ one-click deployable ML project templates)

If the bank is using only CML and not the rest of CDP, the case for Cloudera's additional
licensing cost is significantly weakened. If the bank uses CDW, CDE, and CDF alongside CML,
then the integrated governance and orchestration provides genuine enterprise value.

---

### Finding 3: The capacity utilisation problem is a structural limitation of CML's architecture

CML's minimum resource requirements per workspace are:
- 128 GB RAM (recommended: 256 GB)
- 32 CPU cores (recommended: 32–48 cores)
- 4 TB of block storage
- 1 TB NFS space

When a workspace reaches these limits, new sessions queue or fail. This is not simply
an infrastructure sizing problem — it is a product design choice where CML allocates
resources at the workspace level rather than the session level. Adding more resources
to the cluster resolves the immediate capacity issue, but the same ceiling will be
reached as user count grows.

RHOAI allocates resources per workbench session with configurable resource profiles.
Idle sessions release their resources. This architecture scales more efficiently on
the same underlying hardware.

---

### Finding 4: RHOAI closed three major capability gaps in November 2024

RHOAI version 2.15, released November 12, 2024, added:

**Model Registry:** centralised catalogue of trained models with versions and deployment status.
This closes a gap that previously required external tooling.

**Data Drift Detection (TrustyAI):** real-time monitoring of deployed models detecting when
incoming production data deviates from training data distribution. Critical for maintaining
model accuracy over time in a changing economic environment.

**Bias Detection:** monitors whether deployed models produce unfair outcomes across protected
attributes. This is increasingly required by financial services regulators and was not
previously available in RHOAI.

CML has had drift monitoring since 2020. RHOAI has now matched this capability and added
bias detection that CML does not have natively.

---

### Finding 5: Cloudera AI's governance advantage is real and material in a regulated banking context

Apache Ranger provides column-level access control across datasets. A data scientist can
be permitted to access income and age columns for model training while being blocked from
accessing national IDs, names, and account numbers in the same table. This control is
enforced at the data layer, not dependent on application-level controls.

Apache Atlas automatically records what data every model was trained on, creating an audit
trail that demonstrates regulatory compliance. Central Bank of Egypt requirements for model
risk management increasingly require this kind of evidence.

RHOAI provides namespace-level isolation (different teams cannot access each other's
workbenches) but does not natively provide column-level data access control or automatic
data lineage tracking at the data layer. These capabilities would need to be added through
separate tooling if moving to RHOAI alone.

---

### Finding 6: RHOAI has a stronger open-source foundation and lower vendor lock-in risk

RHOAI is built entirely on open-source components: Kubeflow Pipelines, MLflow, KServe,
TrustyAI, vLLM, and Prometheus. Red Hat provides enterprise support and hardening, but
the underlying code base is community-maintained and vendor-neutral.

Cloudera AI's management and orchestration layer is proprietary. While Cloudera uses
open-source components (Spark, Ranger, Atlas, Airflow), the integration and management
platform is Cloudera intellectual property. Transitioning away from Cloudera requires
re-implementing pipeline orchestration and governance tooling.

For an institution concerned about long-term technology sovereignty and avoiding dependence
on a single vendor, RHOAI's open-source foundation reduces strategic risk.

---

## Head-to-Head Comparison

| Dimension | Cloudera AI (CML) | Red Hat OpenShift AI | Advantage |
|---|---|---|---|
| Deployment model | Runs ON OpenShift (OCP or ECS) | Native OpenShift operator | Equal — same infrastructure |
| Spark integration | Native Spark-on-K8s, one-click | Spark Operator, manual setup required | CML |
| Pipeline orchestration | Apache Airflow (via CDE) | Kubeflow Pipelines v2 | CML for data engineering; RHOAI for ML reproducibility |
| Data governance | Apache Ranger + Atlas (column-level) | Namespace RBAC only | CML |
| Model monitoring | Native metrics + Evidently.ai | TrustyAI (drift + bias detection) | RHOAI (bias) / Equal (drift) |
| Model serving | REST endpoints (simple) | KServe + ModelMesh + vLLM | RHOAI for GenAI workloads |
| Model registry | Available | Added in RHOAI 2.15 (Nov 2024) | Equal |
| Resource efficiency | Heavy (128 GB+ per workspace) | Lighter (per-session profiles) | RHOAI |
| Capacity at scale | Workspace-level ceiling | Session-level allocation | RHOAI |
| GenAI capabilities | AMPs, Hugging Face integration | vLLM, LoRA, Nvidia NIM, AMD GPU | RHOAI |
| Compliance frameworks | GDPR, HIPAA | FedRAMP, PCI DSS, HIPAA, NIST 800-53 | RHOAI (broader certification) |
| Open source | Partial (Spark, Ranger open; orchestration proprietary) | Full (Kubeflow, MLflow, TrustyAI) | RHOAI |
| Vendor lock-in risk | Medium-High | Low | RHOAI |
| Licensing cost | High (CDP license required) | Included in OpenShift subscription or add-on | RHOAI |
| Rapid prototyping | AMPs (130+ templates) | No equivalent | CML |
| Audit trail | Apache Atlas (automated) | Manual or external tooling | CML |

---

## What the Capacity Problem Tells Us

The fact that CML is "fully utilised" is not just an operational inconvenience.
It reveals an architectural characteristic:

CML workspaces have a fixed ceiling. When data scientist usage grows — as it should
in a bank expanding its ML programme — you either allocate more infrastructure to
CML (increasing cost) or users compete for resources (degrading productivity).

RHOAI's session-level resource allocation means resources are reclaimed when sessions
end. The same cluster hardware accommodates more concurrent users at the same cost.

If the ML programme is expected to grow from a small team to a larger one over the
next 18 months, RHOAI's resource model scales more cost-effectively.

---

## Scenarios and Recommendations

### Scenario A: Bank is fully invested in the Cloudera CDP ecosystem

If CDW (SQL analytics), CDE (Spark pipelines), and CDF (data streaming) are all
in production alongside CML, and Apache Ranger is actively enforcing data access
policies, then the integrated Cloudera ecosystem provides genuine enterprise value
that RHOAI alone cannot replicate without significant additional tooling.

**Recommendation in this scenario:** Resolve the capacity issue by expanding CML
resources. The transition cost to RHOAI would exceed the benefit.

### Scenario B: Bank uses only CML, not the rest of CDP

If CML is the only Cloudera product in use and the bank is paying full CDP licensing
for it, the cost-benefit analysis shifts strongly toward RHOAI.

**Recommendation in this scenario:** Run the RHOAI POC to completion. If pipeline
functionality matches requirements, the licensing cost saving and lighter resource
footprint justify migration.

### Scenario C: Parallel operation (recommended near-term)

The POC currently underway should run to completion on RHOAI. This produces an
evidence-based comparison on actual bank infrastructure with actual use cases,
rather than a theoretical debate.

The two platforms can run in parallel on the same OpenShift cluster during evaluation.
Data scientists can compare the experience directly. A time-boxed 90-day parallel
evaluation with defined success criteria (pipeline run time, resource consumption,
governance capability, user adoption) would produce data that makes the decision
defensible to regulators and leadership.

**Recommendation:** Complete the RHOAI POC. Define 5–6 measurable success criteria.
Run both platforms for 90 days. Let the evidence decide.

---

## Risk Assessment

| Risk | Cloudera AI | OpenShift AI |
|---|---|---|
| Capacity ceiling as team grows | High — workspace model has fixed ceiling | Low — session-level allocation scales |
| Governance gap | Low — Ranger + Atlas is production-ready | Medium — no column-level control natively |
| Vendor lock-in | Medium-High — proprietary orchestration | Low — fully open source |
| Licensing cost increase | High — CDP pricing is substantial | Low — included in OpenShift subscription |
| Integration with existing data warehouse | Low — native CDW integration | Medium — requires configuration |
| Model fairness regulatory requirement | Medium — no native bias detection | Low — TrustyAI provides bias detection |
| Spark performance for large-scale ML | Low — native Spark-on-K8s | Medium — manual Spark Operator setup |

---

## Immediate Recommended Actions

1. Clarify CDP usage scope: determine which Cloudera products are actively used
   beyond CML. This single fact changes the recommendation significantly.

2. Verify RHOAI licensing position: confirm whether RHOAI is already included in
   the existing Red Hat OpenShift subscription or requires an additional purchase.

3. Complete the data preparation POC on RHOAI: the pipeline is built and functional
   locally. Running it on the cluster will produce concrete performance and capability data.

4. Define a governance gap remediation plan: if RHOAI is selected, document how
   column-level access control and data lineage will be addressed.

5. Commission a 90-day parallel evaluation with defined KPIs before making
   a permanent platform decision.

---

## Sources

All findings in this document are sourced from:

- Cloudera official documentation (docs.cloudera.com) — CML known issues, runtime requirements,
  architecture specifications
- Red Hat official press release — RHOAI 2.15 announcement, November 12, 2024
- Red Hat blog — "Unlock sensitive data for AI with Cloudera on Red Hat OpenShift,"
  November 25, 2025
- Red Hat blog — "Digital sovereignty for banks," December 2025
- Red Hat Developer documentation — RHOAI components and compliance frameworks
- Cloudera community articles — MLOps with Cloudera AI, CML workspace sizing guidance
- Cloudera release notes — known issues including RBAC vulnerability (TSB 2025-826)
  and garbage collection bug (TSB 2025-844)
- InfoWorld — "Red Hat OpenShift AI unveils model registry, data drift detection,"
  November 12, 2024
- Energent.ai market report — European bank RHOAI deployment case study (40% reduction
  in deployment bottleneck times)
- Cloudera pricing documentation — £97,776/year base enterprise pricing
- Red Hat pricing documentation — OpenShift $0.076/hour reserved, $1,000–$2,500+
  per 2-core pack annually
