#!/usr/bin/env bash
#
# Install Pelorus on OpenShift using the Operator
#
# Builds all images on the cluster (base images pulled from external registries).
# Supports both Red Hat and community operator sources.
#
# Usage:
#   ./demo/install.sh                         # auto-detect (prefer Red Hat)
#   OPERATOR_SOURCE=redhat ./demo/install.sh  # force Red Hat operators
#   OPERATOR_SOURCE=community ./demo/install.sh  # force community operators
#   OAUTH_ENABLED=false ./demo/install.sh        # disable OAuth proxy (basic auth)
#
set -euo pipefail

NAMESPACE="${NAMESPACE:-pelorus}"
OPERATOR_NS="${NAMESPACE}-operator-system"
TIMEOUT="${TIMEOUT:-900}"
POLL=10
OPERATOR_SOURCE="${OPERATOR_SOURCE:-auto}"
PELORUS_PASSWORD="${PELORUS_PASSWORD:-$(openssl rand -base64 12)}"
OAUTH_ENABLED="${OAUTH_ENABLED:-true}"

log() { echo "[$(date +%H:%M:%S)] $*"; }
fail() { log "FAIL: $*" >&2; exit 1; }

wait_for_build() {
  local name="$1" timeout="${2:-$TIMEOUT}"
  log "Waiting for build $name..."
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local phase
    phase=$(oc get builds -n "$NAMESPACE" --no-headers 2>/dev/null \
      | grep "$name" | tail -1 | awk '{print $4}' || echo "")
    if [[ "$phase" == "Complete" ]]; then
      log "Build $name complete"
      return 0
    elif [[ "$phase" == "Failed" || "$phase" == "Error" ]]; then
      oc logs "build/${name}" -n "$NAMESPACE" 2>&1 | tail -10
      fail "Build $name failed"
    fi
    sleep "$POLL"
    elapsed=$((elapsed + POLL))
  done
  fail "Timed out waiting for build $name"
}

wait_for_csv() {
  local name="$1" timeout="${2:-$TIMEOUT}"
  log "Waiting for operator $name..."
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local phase
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

log "========================================="
log "Installing Pelorus on OpenShift"
log "  Operator source: $OPERATOR_SOURCE"
log "  OAuth proxy:     $OAUTH_ENABLED"
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
  source: community-operators
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
fi

# 3. Build exporter image
log "Building exporter image..."
ln -sf Containerfile exporters/Dockerfile
oc new-build --name=pelorus-exporter --strategy=docker --binary \
  -n "$NAMESPACE" 2>/dev/null || true
oc start-build pelorus-exporter --from-dir=exporters \
  -n "$NAMESPACE" --follow 2>&1 | tail -5
wait_for_build "pelorus-exporter-" 600

# 4. Build operator image
log "Building operator image..."
oc new-build --name=pelorus-operator --strategy=docker --binary \
  -n "$NAMESPACE" 2>/dev/null || true
oc start-build pelorus-operator --from-dir=pelorus-operator \
  -n "$NAMESPACE" --follow 2>&1 | tail -5
wait_for_build "pelorus-operator-" 600

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

log "Creating Pelorus instance (operator_source=$OPERATOR_SOURCE)..."
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
  prometheus_retention: 1y
  prometheus_retention_size: 1GB
  prometheus_storage: false
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
log "Pelorus installed successfully"
log "  Operator source: $OPERATOR_SOURCE"
log "  OAuth proxy:     $OAUTH_ENABLED"
log "========================================="
echo ""
echo "  Grafana:  https://${GRAFANA_ROUTE:-pending}"
echo "  Login:    admin / <password from \$PELORUS_PASSWORD>"
echo ""
echo "  Next steps:"
echo "    ./demo/setup-demo.sh      # seed data and verify (one command)"
echo "    ./demo/seed-metrics.sh    # seed data only"
echo ""
