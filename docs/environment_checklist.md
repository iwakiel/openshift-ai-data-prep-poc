# RHOAI Environment Checklist

A seven-step verification checklist to confirm OpenShift AI is properly configured for the data preparation POC. Designed to run as a single script in one privileged access session.

---

## Quick Run

```bash
./scripts/verify_rhoai_env.sh --namespace <your-namespace>
```

---

## Manual Checks

### 1. RHOAI Operator Status

Verify the Red Hat OpenShift AI operator is installed and in `Succeeded` state. Minimum required version: `2.x`.

```bash
oc get csv -n redhat-ods-operator | grep -iE "rhods|openshift-ai"
oc get DataScienceCluster -o jsonpath='{.items[0].status.phase}'
```

**Expected:** `Succeeded` / `Ready`  
**Blocker if missing:** RHOAI not installed — requires cluster-admin to install the operator.

---

### 2. Storage Backend (MinIO / ODF)

Confirm S3-compatible object storage is available for pipeline artifacts and datasets.

```bash
oc get pods -n redhat-ods-applications | grep -iE "minio|ceph|noobaa"
oc get storageclasses
```

**Expected:** MinIO pods in `Running` state, or ODF/NooBaa storage class available.  
**Blocker if missing:** No storage backend = no pipeline artifacts, no dataset persistence.

---

### 3. Data Science Pipeline Server (DSPA)

Verify the pipeline server is provisioned in your project namespace. Without this, Kubeflow Pipelines v2 cannot run.

```bash
oc get dspa -n <your-namespace>
oc get pods -n <your-namespace> | grep ds-pipeline
```

**Expected:** DSPA resource exists, pipeline pods in `Running` state.  
**Blocker if missing:** Request provisioning from platform team. ETA: 1–2 business days.

---

### 4. Workbench Runtime Images

Check that Python 3.9+ notebook images are available, and optionally a Spark-enabled image.

```bash
oc get imagestreams -n redhat-ods-applications --no-headers | awk '{print $1}'
```

**Expected:** At minimum, a standard Data Science notebook image (Python 3.9).  
**Optional:** Spark-enabled image for PySpark workloads.

---

### 5. Namespace Resource Quotas

Confirm your namespace has sufficient CPU and memory allocation for the planned workloads.

```bash
oc get resourcequota -n <your-namespace>
oc get limitrange -n <your-namespace>
```

**Required minimums:**
- EDA notebook: 2 CPU / 8Gi RAM
- Pipeline run: 4 CPU / 16Gi RAM

---

### 6. S3 Connectivity from Workbench

Validate that workbench pods can reach the MinIO endpoint (network policies may block this).

Run inside a test notebook:

```python
import boto3, os

s3 = boto3.client(
    's3',
    endpoint_url=os.getenv('MINIO_ENDPOINT'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Should return bucket list without error
print(s3.list_buckets())
```

**Expected:** Returns bucket list (even if empty).  
**Blocker if failing:** Network policy exception needed from platform team.

---

### 7. Python Package Access

Verify required packages can be installed. Banks often restrict internet access from cluster pods.

Run inside a test notebook:

```bash
pip install great-expectations kfp sdv ydata-profiling --quiet
```

**Expected:** Packages install successfully.  
**If blocked:** Request the internal PyPI mirror URL (Nexus/Artifactory) from the platform team, then use:

```bash
pip install great-expectations --index-url http://nexus.<internal-domain>/pypi/simple/
```

---

## Status Tracker

| # | Check | Status | Notes |
|---|---|---|---|
| 1 | RHOAI operator | ⬜ Pending | |
| 2 | Storage backend | ⬜ Pending | |
| 3 | DSPA pipeline server | ⬜ Pending | |
| 4 | Runtime images | ⬜ Pending | |
| 5 | Resource quotas | ⬜ Pending | |
| 6 | S3 connectivity | ⬜ Pending | |
| 7 | PyPI access | ⬜ Pending | |

Legend: ✅ Pass | ❌ Blocked | ⬜ Pending | ⚠️ Partial
