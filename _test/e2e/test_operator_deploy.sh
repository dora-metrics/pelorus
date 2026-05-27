#!/usr/bin/env bash
#
# E2E Test: Build on OpenShift + deploy with Pelorus Operator
#
# Tests the full workflow:
#   1. Build exporter image on OpenShift
#   2. Build Pelorus Operator image on OpenShift
#   3. Install Prometheus and Grafana operators
#   4. Deploy the Pelorus Operator using the built image
#   5. Create a Pelorus CR with image overrides
#   6. Send test metrics via webhook
#   7. Verify metrics in Prometheus and dashboards in Grafana
#   8. Clean up
#
# Usage:
#   ./_test/e2e/test_operator_deploy.sh
#   SKIP_CLEANUP=1 ./_test/e2e/test_operator_deploy.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

SKIP_CLEANUP="${SKIP_CLEANUP:-0}"
OPERATOR_NS="${NAMESPACE}-operator-system"

cleanup_operator() {
  log "Cleaning up operator resources..."
  oc delete pelorus --all -n "$NAMESPACE" 2>/dev/null || true
  sleep 5
  cd pelorus-operator && make undeploy 2>/dev/null || true; cd ..
  oc delete bc pelorus-operator -n "$NAMESPACE" 2>/dev/null || true
  oc delete is pelorus-operator -n "$NAMESPACE" 2>/dev/null || true
  oc delete namespace "$OPERATOR_NS" 2>/dev/null || true
  cleanup
}

trap '[[ "$SKIP_CLEANUP" == "0" ]] && cleanup_operator' EXIT

log "============================================"
log "E2E Test: Build on OCP + Operator deploy"
log "============================================"

# 1. Setup
create_namespace
install_operators

# 2. Build exporter image on OpenShift
log "Building exporter image on OpenShift..."
ln -sf Containerfile exporters/Dockerfile
oc new-build --name=pelorus-exporter --strategy=docker --binary \
  -n "$NAMESPACE" 2>/dev/null || true
oc start-build pelorus-exporter --from-dir=exporters \
  -n "$NAMESPACE" --follow 2>&1 | tail -5
wait_for_build "pelorus-exporter-" 600
pass "Exporter image built"

# 3. Build Pelorus Operator image on OpenShift
log "Building Pelorus Operator image on OpenShift..."
oc new-build --name=pelorus-operator --strategy=docker --binary \
  -n "$NAMESPACE" 2>/dev/null || true
oc start-build pelorus-operator --from-dir=pelorus-operator \
  -n "$NAMESPACE" --follow 2>&1 | tail -5
wait_for_build "pelorus-operator-" 600
pass "Operator image built"

REGISTRY=$(get_internal_registry)
OPERATOR_IMG="$REGISTRY/$NAMESPACE/pelorus-operator:latest"
log "Operator image: $OPERATOR_IMG"

# 4. Deploy the operator using the built image
OPERATOR_NS="pelorus-operator-system"
log "Deploying Pelorus Operator..."
cd pelorus-operator
make deploy IMG="$OPERATOR_IMG" 2>&1 | tail -5
cd ..

# Grant the operator SA permission to pull images from our build namespace
log "Granting image pull access to operator SA..."
oc policy add-role-to-user system:image-puller \
  "system:serviceaccount:${OPERATOR_NS}:pelorus-operator-controller-manager" \
  --namespace="$NAMESPACE" 2>/dev/null || true

# Wait for operator pod
log "Waiting for operator pod in $OPERATOR_NS..."
local_elapsed=0
while [[ $local_elapsed -lt 180 ]]; do
  ready=$(oc get pods -n "$OPERATOR_NS" -l control-plane=controller-manager \
    --no-headers 2>/dev/null | grep -c "Running" || true)
  ready=$(echo "$ready" | tr -d '[:space:]')
  if [[ "${ready:-0}" -ge 1 ]]; then
    break
  fi
  sleep 10
  local_elapsed=$((local_elapsed + 10))
done
[[ "${ready:-0}" -ge 1 ]] || fail "Operator pod not running in $OPERATOR_NS"
pass "Pelorus Operator is running"

# 5. Create Pelorus CR with image tag overrides
log "Creating Pelorus CR..."
oc apply -n "$NAMESPACE" -f - <<EOF
apiVersion: charts.pelorus.dora-metrics.io/v1alpha1
kind: Pelorus
metadata:
  name: pelorus-e2e
spec:
  openshift_prometheus_htpasswd_auth: "internal:{SHA}+pvrmeQCmtWmYVOZ57uuITVghrM="
  openshift_prometheus_basic_auth_pass: changeme
  oauth_proxy_enabled: true
  prometheus_retention: 1y
  prometheus_retention_size: 1GB
  prometheus_storage: false
  exporters:
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
        image_tag: latest
      - app_name: committime-exporter
        exporter_type: committime
        image_tag: latest
      - app_name: webhook-exporter
        exporter_type: webhook
        image_tag: latest
      - app_name: failuretime-exporter
        exporter_type: failure
        image_tag: latest
EOF
pass "Pelorus CR created"

# 6. Wait for operator to reconcile and deploy everything
log "Waiting for operator to reconcile..."
sleep 30

# Tag ImageStreams created by the operator/helm with our built image
log "Tagging ImageStreams with built exporter image..."
for t in deploytime committime webhook failuretime; do
  oc tag "pelorus-exporter:latest" "${t}-exporter:stable" -n "$NAMESPACE" 2>/dev/null || true
done
pass "ImageStreams tagged"

wait_for_pods "app.kubernetes.io/name=deploytime-exporter" 1 180
wait_for_pods "app.kubernetes.io/name=webhook-exporter" 1 120

# 7. Wait for Prometheus and Grafana
wait_for_pods "prometheus=prometheus-pelorus" 1 120
wait_for_pods "app=grafana-oauth" 1 180
verify_grafana

# 8. Send test metrics and verify
send_test_metrics
verify_prometheus_metrics

# 9. Verify the Pelorus CR exists
log "Checking Pelorus CR..."
oc get pelorus pelorus-e2e -n "$NAMESPACE" --no-headers 2>&1
pass "Pelorus CR is deployed"

log "============================================"
log "E2E Test PASSED: Operator deploy"
log "============================================"
