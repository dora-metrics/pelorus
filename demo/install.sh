#!/usr/bin/env bash
#
# Install or Update Pelorus on OpenShift using the Operator
#
# This script is idempotent and can be re-run to update configurations.
# Builds all images on the cluster (base images pulled from external registries).
# Supports both Red Hat and community operator sources.
# Enables Prometheus admin API for demo/development use (allows metric deletion).
#
# Usage:
#   ./demo/install.sh                         # auto-detect (prefer Red Hat)
#   OPERATOR_SOURCE=redhat ./demo/install.sh  # force Red Hat operators
#   OPERATOR_SOURCE=community ./demo/install.sh  # force community operators
#   OAUTH_ENABLED=false ./demo/install.sh        # disable OAuth proxy (basic auth)
#   FORCE_REBUILD=true ./demo/install.sh         # force rebuild all images
#
# Re-running:
#   The script is idempotent - it safely updates existing resources:
#   - Skips image builds if images already exist (unless FORCE_REBUILD=true)
#   - Updates Pelorus CR with new configuration values
#   - Recreates resources using declarative 'oc apply'
#
set -euo pipefail

NAMESPACE="${NAMESPACE:-pelorus}"
OPERATOR_NS="${NAMESPACE}-operator-system"
TIMEOUT="${TIMEOUT:-900}"
POLL=10
OPERATOR_SOURCE="${OPERATOR_SOURCE:-auto}"
PELORUS_PASSWORD="${PELORUS_PASSWORD:-$(openssl rand -base64 12)}"
OAUTH_COOKIE_SECRET="${OAUTH_COOKIE_SECRET:-$(openssl rand -base64 24)}"
OAUTH_ENABLED="${OAUTH_ENABLED:-true}"
FORCE_REBUILD="${FORCE_REBUILD:-false}"

log() { echo "[$(date +%H:%M:%S)] $*"; }
fail() { log "FAIL: $*" >&2; exit 1; }

wait_for_build() {
  local build_config="$1" timeout="${2:-$TIMEOUT}"
  log "Waiting for build $build_config..."
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local phase latest_build
    # Get the latest build for this BuildConfig
    latest_build=$(oc get builds -n "$NAMESPACE" --no-headers 2>/dev/null \
      | grep "^${build_config}-" | tail -1 | awk '{print $1}' || echo "")

    if [[ -z "$latest_build" ]]; then
      log "No builds found for $build_config yet..."
      sleep "$POLL"
      elapsed=$((elapsed + POLL))
      continue
    fi

    phase=$(oc get build "$latest_build" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")

    if [[ "$phase" == "Complete" ]]; then
      log "Build $build_config complete"
      return 0
    elif [[ "$phase" == "Failed" || "$phase" == "Error" || "$phase" == "Cancelled" ]]; then
      oc logs "build/${latest_build}" -n "$NAMESPACE" 2>&1 | tail -10
      fail "Build $build_config failed"
    fi
    sleep "$POLL"
    elapsed=$((elapsed + POLL))
  done
  fail "Timed out waiting for build $build_config"
}

check_image_exists() {
  local name="$1"
  # Check if ImageStream exists and has at least one tag
  if oc get is "$name" -n "$NAMESPACE" &>/dev/null; then
    local tags
    tags=$(oc get is "$name" -n "$NAMESPACE" -o jsonpath='{.status.tags[*].tag}' 2>/dev/null || echo "")
    [[ -n "$tags" ]]
  else
    return 1
  fi
}

wait_for_csv() {
  local name="$1" timeout="${2:-$TIMEOUT}"
  local phase
  phase=$(oc get csv -n "$NAMESPACE" --no-headers 2>/dev/null \
    | grep "$name" | awk '{print $NF}' || echo "")

  # If already succeeded, return immediately
  if [[ "$phase" == "Succeeded" ]]; then
    log "Operator $name already installed"
    return 0
  fi

  log "Waiting for operator $name..."
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    phase=$(oc get csv -n "$NAMESPACE" --no-headers 2>/dev/null \
      | grep "$name" | awk '{print $NF}' || echo "")
    [[ "$phase" == "Succeeded" ]] && return 0
    sleep "$POLL"
    elapsed=$((elapsed + POLL))
  done
  fail "Timed out waiting for operator $name"
}

# Auto-detect: prefer Red Hat operators if available
if [[ "$OPERATOR_SOURCE" == "auto" ]]; then
  if oc get pods -n openshift-monitoring -l app.kubernetes.io/name=prometheus-operator --no-headers 2>/dev/null | grep -q Running; then
    OPERATOR_SOURCE="redhat"
  else
    OPERATOR_SOURCE="community"
  fi
  log "Auto-detected operator source: $OPERATOR_SOURCE"
fi

# Check if this is an initial install or update
if oc get pelorus pelorus -n "$NAMESPACE" &>/dev/null 2>&1; then
  INSTALL_MODE="Updating"
else
  INSTALL_MODE="Installing"
fi

log "========================================="
log "$INSTALL_MODE Pelorus on OpenShift"
log "  Operator source: $OPERATOR_SOURCE"
log "  OAuth proxy:     $OAUTH_ENABLED"
log "  Prometheus:      1 replica (dev mode)"
log "========================================="

# 1. Namespace
log "Creating namespace $NAMESPACE..."
oc create namespace "$NAMESPACE" 2>/dev/null || true
sleep 3

# 2. Install operators based on source
#    redhat: Uses OpenShift user workload monitoring (built-in Prometheus scrapes
#            ServiceMonitors and evaluates PrometheusRules in user namespaces).
#            Grafana via community Grafana Operator (COO provides CRDs only).
#    community: Uses community Prometheus Operator + community Grafana Operator.
if [[ "$OPERATOR_SOURCE" == "redhat" ]]; then
  log "Using OpenShift built-in monitoring (Prometheus)"
  log "Enabling user workload monitoring..."
  oc apply -f - <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-monitoring-config
  namespace: openshift-monitoring
data:
  config.yaml: |
    enableUserWorkload: true
EOF

  # Wait for user workload monitoring
  log "Waiting for user workload monitoring pods..."
  elapsed=0
  while [[ $elapsed -lt 180 ]]; do
    ready=$(oc get pods -n openshift-user-workload-monitoring --no-headers 2>/dev/null | grep -c Running || true)
    ready=$(echo "$ready" | tr -d '[:space:]')
    [[ "${ready:-0}" -ge 1 ]] && break
    sleep "$POLL"
    elapsed=$((elapsed + POLL))
  done
  log "User workload monitoring is running"

  log "Installing Cluster Observability Operator (Grafana)..."
  # COO requires AllNamespaces install mode - install in openshift-operators
  oc apply -f - <<'EOF'
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: cluster-observability-operator
  namespace: openshift-operators
spec:
  channel: stable
  name: cluster-observability-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
EOF
  log "Waiting for COO..."
  elapsed=0
  while [[ $elapsed -lt "$TIMEOUT" ]]; do
    phase=$(oc get csv -n openshift-operators --no-headers 2>/dev/null \
      | grep "cluster-observability-operator" | awk '{print $NF}' || echo "")
    [[ "$phase" == "Succeeded" ]] && break
    sleep "$POLL"
    elapsed=$((elapsed + POLL))
  done
  [[ "$phase" == "Succeeded" ]] || fail "COO install failed"
  log "Cluster Observability Operator installed"

  # Create OperatorGroup (needed for Grafana Operator subscription)
  # No community Prometheus Operator needed - user workload monitoring
  # handles ServiceMonitor and PrometheusRule scraping/evaluation.
  oc apply -n "$NAMESPACE" -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: pelorus-og
spec:
  targetNamespaces:
    - $NAMESPACE
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: grafana-operator
spec:
  channel: v5
  name: grafana-operator
  source: community-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
EOF
  wait_for_csv "grafana-operator"

else
  log "Installing community Prometheus and Grafana operators..."

  # TODO: TEMPORARY WORKAROUND - Remove this when OpenShift community-operators is updated
  # The OpenShift community-operators catalog only has Prometheus Operator v0.56.3 (from 2022)
  # which doesn't support additionalArgs needed for out-of-order ingestion.
  # We're temporarily using the k8s-operatorhub catalog which has v0.70.0.
  # This should be removed once OpenShift community-operators catches up.
  # See: demo/ADD_OPERATORHUBIO_CATALOG.md for details
  log "Adding k8s-operatorhub catalog source (temporary workaround for demo)..."
  oc apply -f - <<'EOF'
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: operatorhubio-catalog
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: quay.io/operatorhubio/catalog:latest
  displayName: OperatorHub.io Operators
  publisher: OperatorHub.io
  updateStrategy:
    registryPoll:
      interval: 60m
EOF

  log "Waiting for operatorhubio-catalog to sync..."
  sleep 15

  # NOTE: Using operatorhubio-catalog to get Prometheus Operator v0.70.0
  # which supports additionalArgs required for out-of-order ingestion
  oc apply -n "$NAMESPACE" -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: pelorus-og
spec:
  targetNamespaces:
    - $NAMESPACE
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: prometheus
spec:
  channel: beta
  name: prometheus
  source: operatorhubio-catalog  # TODO: Change back to community-operators when it's updated
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: grafana-operator
spec:
  channel: v5
  name: grafana-operator
  source: community-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
EOF
  wait_for_csv "prometheusoperator"
  wait_for_csv "grafana-operator"

  # Verify Prometheus Operator version supports additionalArgs (required for OOO ingestion)
  log "Verifying Prometheus Operator version..."
  prom_op_version=$(oc get csv -n "$NAMESPACE" -o jsonpath='{.items[?(@.metadata.name=="prometheusoperator.*")].spec.version}' 2>/dev/null || echo "unknown")
  log "Prometheus Operator version: $prom_op_version"

  if [[ "$prom_op_version" != "unknown" ]]; then
    # Extract major.minor version (e.g., "0.70.0" -> "70")
    minor_version=$(echo "$prom_op_version" | cut -d. -f2)
    if [[ "$minor_version" -lt 59 ]]; then
      log "WARNING: Prometheus Operator v$prom_op_version does not support additionalArgs"
      log "WARNING: Out-of-order ingestion requires v0.59.0+. Historical backfill will NOT work."
      log "WARNING: Consider using operatorhubio-catalog for v0.70.0"
    else
      log "✓ Prometheus Operator v$prom_op_version supports out-of-order ingestion"
    fi
  fi
fi

# 3. Build exporter image
log "Ensuring exporter BuildConfig exists..."
ln -sf Containerfile exporters/Dockerfile

# Create BuildConfig declaratively
oc apply -n "$NAMESPACE" -f - <<EOF
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: pelorus-exporter
spec:
  output:
    to:
      kind: ImageStreamTag
      name: pelorus-exporter:latest
  source:
    type: Binary
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Dockerfile
EOF

# Create ImageStream if it doesn't exist
oc apply -n "$NAMESPACE" -f - <<EOF
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: pelorus-exporter
EOF

# Only start a new build if image doesn't exist or force rebuild
if [[ "$FORCE_REBUILD" == "true" ]] || ! check_image_exists "pelorus-exporter"; then
  log "Building exporter image..."
  oc start-build pelorus-exporter --from-dir=exporters \
    -n "$NAMESPACE" --follow 2>&1 | tail -5 &
  wait_for_build "pelorus-exporter" 600
else
  log "Exporter image already exists, skipping build (set FORCE_REBUILD=true to rebuild)"
fi

# 4. Build operator image
log "Ensuring operator BuildConfig exists..."

# Create BuildConfig declaratively
oc apply -n "$NAMESPACE" -f - <<EOF
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: pelorus-operator
spec:
  output:
    to:
      kind: ImageStreamTag
      name: pelorus-operator:latest
  source:
    type: Binary
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Dockerfile
EOF

# Create ImageStream if it doesn't exist
oc apply -n "$NAMESPACE" -f - <<EOF
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: pelorus-operator
EOF

# Only start a new build if image doesn't exist or force rebuild
if [[ "$FORCE_REBUILD" == "true" ]] || ! check_image_exists "pelorus-operator"; then
  log "Building operator image..."
  oc start-build pelorus-operator --from-dir=pelorus-operator \
    -n "$NAMESPACE" --follow 2>&1 | tail -5 &
  wait_for_build "pelorus-operator" 600
else
  log "Operator image already exists, skipping build (set FORCE_REBUILD=true to rebuild)"
fi

REGISTRY="image-registry.openshift-image-registry.svc:5000"
OPERATOR_IMG="$REGISTRY/$NAMESPACE/pelorus-operator:latest"

# 5. Deploy operator
log "Deploying Pelorus Operator ($OPERATOR_IMG)..."
cd pelorus-operator
make deploy IMG="$OPERATOR_IMG" 2>&1 | tail -5
cd ..

log "Granting image pull access..."
oc policy add-role-to-user system:image-puller \
  "system:serviceaccount:${OPERATOR_NS}:pelorus-operator-controller-manager" \
  --namespace="$NAMESPACE" 2>/dev/null || true
oc policy add-role-to-group system:image-puller \
  "system:serviceaccounts:${NAMESPACE}" \
  --namespace="$NAMESPACE" 2>/dev/null || true

log "Waiting for operator..."
elapsed=0
while [[ $elapsed -lt 180 ]]; do
  ready=$(oc get pods -n "$OPERATOR_NS" -l control-plane=controller-manager \
    --no-headers 2>/dev/null | grep -c "Running" || true)
  ready=$(echo "$ready" | tr -d '[:space:]')
  [[ "${ready:-0}" -ge 1 ]] && break
  sleep "$POLL"
  elapsed=$((elapsed + POLL))
done
[[ "${ready:-0}" -ge 1 ]] || fail "Operator not running"
log "Operator is running"

# 6. Create Pelorus CR
HTPASSWD_FIELD=""
if [[ "$OAUTH_ENABLED" == "true" && "$OPERATOR_SOURCE" == "community" ]]; then
  HTPASSWD=$(htpasswd -s -b -n internal "$PELORUS_PASSWORD" 2>/dev/null) || \
    HTPASSWD="internal:{SHA}$(echo -n "$PELORUS_PASSWORD" | openssl dgst -sha1 -binary | base64)"
  HTPASSWD_FIELD="openshift_prometheus_htpasswd_auth: \"$HTPASSWD\""
fi

# Check if Pelorus CR already exists
if oc get pelorus pelorus -n "$NAMESPACE" &>/dev/null; then
  log "Updating existing Pelorus instance (operator_source=$OPERATOR_SOURCE)..."
else
  log "Creating Pelorus instance (operator_source=$OPERATOR_SOURCE)..."
fi

oc apply -n "$NAMESPACE" -f - <<EOF
apiVersion: charts.pelorus.dora-metrics.io/v1alpha1
kind: Pelorus
metadata:
  name: pelorus
spec:
  openshift_prometheus_basic_auth_pass: "$PELORUS_PASSWORD"
  $HTPASSWD_FIELD
  operator_source: $OPERATOR_SOURCE
  oauth_proxy_enabled: $OAUTH_ENABLED
  prometheus_oauth_cookie_secret: "$OAUTH_COOKIE_SECRET"
  prometheus_retention: 1y
  prometheus_retention_size: 1GB
  # Enable persistent storage for Prometheus (required for backfilled demo data to survive pod restarts)
  prometheus_storage: true
  prometheus_storage_pvc_capacity: 5Gi
  # Use 1 replica for single-node dev environments (default is 2 for HA)
  prometheus_replicas: 1
  # Enable admin API for demo seed/clear scripts
  prometheus_enable_admin_api: true
  # Enable out-of-order ingestion for 6-month historical demo data
  prometheus_out_of_order_time_window: 180d
  exporters:
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
        image_name: $REGISTRY/$NAMESPACE/pelorus-exporter:latest
      - app_name: committime-exporter
        exporter_type: committime
        image_name: $REGISTRY/$NAMESPACE/pelorus-exporter:latest
      - app_name: webhook-exporter
        exporter_type: webhook
        image_name: $REGISTRY/$NAMESPACE/pelorus-exporter:latest
        extraEnv:
          # Allow backdated metrics (up to 1 year old) for demo seed script
          - name: PELORUS_TIMESTAMP_THRESHOLD_MINUTES
            value: "525600"
      - app_name: failuretime-exporter
        exporter_type: failure
        image_name: $REGISTRY/$NAMESPACE/pelorus-exporter:latest
EOF

# 7. Tag ImageStreams
log "Waiting for operator to create resources..."
sleep 30
log "Tagging ImageStreams with built exporter image..."
for t in deploytime committime webhook failuretime; do
  oc tag "pelorus-exporter:latest" "${t}-exporter:stable" -n "$NAMESPACE" 2>/dev/null || true
  # Label ImageStreams so Helm can adopt them
  oc label is "${t}-exporter" -n "$NAMESPACE" app.kubernetes.io/managed-by=Helm --overwrite 2>/dev/null || true
  oc annotate is "${t}-exporter" -n "$NAMESPACE" meta.helm.sh/release-name=pelorus meta.helm.sh/release-namespace="$NAMESPACE" --overwrite 2>/dev/null || true
done

# 8. Wait for exporters to be ready
log "Waiting for exporter pods..."
elapsed=0
while [[ $elapsed -lt "$TIMEOUT" ]]; do
  ready=$(oc get pods -n "$NAMESPACE" -l pelorus.dora-metrics.io/exporter-type --no-headers 2>/dev/null | grep -c "Running" || true)
  ready=$(echo "$ready" | tr -d '[:space:]')
  [[ "${ready:-0}" -ge 4 ]] && break
  sleep "$POLL"
  elapsed=$((elapsed + POLL))
done

oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | \
  grep -v operator | grep -v build | \
  awk '{printf "  %-50s %s\n", $1, $3}'

# 9. Ensure monitoring RBAC for Grafana (redhat path needs cluster-monitoring-view)
if [[ "$OPERATOR_SOURCE" == "redhat" ]]; then
  log "Ensuring Grafana monitoring access..."
  oc create clusterrolebinding pelorus-grafana-cluster-monitoring-view \
    --clusterrole=cluster-monitoring-view \
    --serviceaccount="${NAMESPACE}:grafana-sa" 2>/dev/null || true
fi

# 10. Ensure Grafana Operator syncs dashboards
log "Syncing Grafana dashboards..."
oc delete pod -n "$NAMESPACE" -l app.kubernetes.io/name=grafana-operator --force 2>/dev/null || true
sleep 20

# Wait for Grafana route
elapsed=0
while [[ $elapsed -lt 120 ]]; do
  GRAFANA_ROUTE=$(oc get route grafana-route -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
  [[ -n "$GRAFANA_ROUTE" ]] && break
  sleep "$POLL"
  elapsed=$((elapsed + POLL))
done

log "========================================="
if [[ "$INSTALL_MODE" == "Installing" ]]; then
  log "Pelorus installed successfully"
else
  log "Pelorus updated successfully"
fi
log "  Operator source: $OPERATOR_SOURCE"
log "  OAuth proxy:     $OAUTH_ENABLED"
log "  Admin API:       enabled (for demo/development)"
log "========================================="
echo ""
echo "  Grafana:  https://${GRAFANA_ROUTE:-pending}"
echo "  Login:    admin / <password from \$PELORUS_PASSWORD>"
echo ""
echo "  Next steps:"
echo "    ./demo/seed-metrics.sh    # load 6 months of sample DORA metrics"
echo "    ./demo/clear-metrics.sh   # clear all metrics (before re-seeding)"
echo ""
echo "  To update configuration:"
echo "    Edit this script and re-run it - it's idempotent!"
echo "    To force rebuild images: FORCE_REBUILD=true ./demo/install.sh"
echo ""
echo "  Note: Prometheus admin API is enabled for demo/dev use."
echo "        Do not enable in production environments."
echo ""
