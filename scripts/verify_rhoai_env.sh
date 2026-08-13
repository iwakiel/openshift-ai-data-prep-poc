#!/usr/bin/env bash
# ============================================================
# verify_rhoai_env.sh
# One-shot RHOAI environment verification for the data prep POC.
# Designed to run in a single BeyondTrust privileged session.
# ============================================================

set -euo pipefail

NAMESPACE="${1:-}"
PASS="✅"
FAIL="❌"
WARN="⚠️ "

usage() {
  echo "Usage: $0 --namespace <openshift-namespace>"
  echo "Example: $0 --namespace mlops-poc"
  exit 1
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace|-n) NAMESPACE="$2"; shift 2 ;;
    --help|-h)      usage ;;
    *)              shift ;;
  esac
done

[[ -z "$NAMESPACE" ]] && usage

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  RHOAI Environment Verification"
echo "  Namespace: $NAMESPACE"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════"
echo ""

PASS_COUNT=0
FAIL_COUNT=0

check() {
  local label="$1"
  local cmd="$2"
  local expected="$3"

  echo -n "  [$label] ... "
  output=$(eval "$cmd" 2>&1 || true)

  if echo "$output" | grep -qi "$expected"; then
    echo "$PASS"
    ((PASS_COUNT++))
  else
    echo "$FAIL"
    echo "    → Output: $(echo "$output" | head -3)"
    ((FAIL_COUNT++))
  fi
}

# ── 1. RHOAI Operator ────────────────────────────────────────
echo "[ 1 ] RHOAI Operator"
check \
  "CSV status" \
  "oc get csv -n redhat-ods-operator 2>/dev/null | grep -iE 'rhods|openshift-ai'" \
  "Succeeded"

check \
  "DataScienceCluster" \
  "oc get datasciencecluster -o jsonpath='{.items[0].status.phase}' 2>/dev/null" \
  "Ready"
echo ""

# ── 2. Storage Backend ───────────────────────────────────────
echo "[ 2 ] Storage Backend (MinIO / ODF)"
check \
  "MinIO pods" \
  "oc get pods -n redhat-ods-applications 2>/dev/null | grep -iE 'minio|noobaa|ceph'" \
  "Running"

echo -n "  [Storage classes] ... "
SC_COUNT=$(oc get storageclasses --no-headers 2>/dev/null | wc -l)
if [[ "$SC_COUNT" -gt 0 ]]; then
  echo "$PASS ($SC_COUNT found)"
  ((PASS_COUNT++))
else
  echo "$FAIL (none found)"
  ((FAIL_COUNT++))
fi
echo ""

# ── 3. Data Science Pipeline Server ─────────────────────────
echo "[ 3 ] Data Science Pipeline Application (DSPA)"
check \
  "DSPA resource" \
  "oc get dspa -n $NAMESPACE 2>/dev/null" \
  "."

check \
  "Pipeline pods" \
  "oc get pods -n $NAMESPACE 2>/dev/null | grep ds-pipeline" \
  "Running"
echo ""

# ── 4. Runtime Images ────────────────────────────────────────
echo "[ 4 ] Workbench Runtime Images"
echo -n "  [ImageStreams] ... "
IS_OUTPUT=$(oc get imagestreams -n redhat-ods-applications --no-headers 2>/dev/null)
IS_COUNT=$(echo "$IS_OUTPUT" | grep -c "." || true)
if [[ "$IS_COUNT" -gt 0 ]]; then
  echo "$PASS ($IS_COUNT images)"
  echo "$IS_OUTPUT" | awk '{print "    →", $1}'
  ((PASS_COUNT++))
else
  echo "$FAIL (no images found)"
  ((FAIL_COUNT++))
fi
echo ""

# ── 5. Resource Quotas ───────────────────────────────────────
echo "[ 5 ] Namespace Resource Quotas"
echo "  Resource quota:"
oc get resourcequota -n "$NAMESPACE" 2>/dev/null || echo "    $WARN No quota set (unlimited)"
echo "  Limit ranges:"
oc get limitrange -n "$NAMESPACE" 2>/dev/null || echo "    $WARN No limit ranges set"
((PASS_COUNT++))
echo ""

# ── 6. Network Policies ──────────────────────────────────────
echo "[ 6 ] Network Policies"
NP_COUNT=$(oc get networkpolicies -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
echo -n "  [NetworkPolicies] ... "
if [[ "$NP_COUNT" -gt 0 ]]; then
  echo "$WARN ($NP_COUNT policies found — verify workbench→S3 is allowed)"
  oc get networkpolicies -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{print "    →", $1}'
  ((PASS_COUNT++))
else
  echo "$PASS (no restrictive policies — S3 access likely open)"
  ((PASS_COUNT++))
fi
echo ""

# ── 7. MLflow ────────────────────────────────────────────────
echo "[ 7 ] MLflow Tracking Server"
check \
  "MLflow pods" \
  "oc get pods -n $NAMESPACE 2>/dev/null | grep -i mlflow" \
  "Running"
echo ""

# ── Summary ──────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════"
echo "  Summary: $PASS_COUNT passed | $FAIL_COUNT failed"
echo "═══════════════════════════════════════════════════════"
echo ""

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "  ❗ Action required: resolve $FAIL_COUNT failing check(s) before proceeding."
  echo "  See docs/environment_checklist.md for remediation steps."
  exit 1
else
  echo "  🚀 Environment is POC-ready. Proceed to data generation."
  exit 0
fi
