#!/usr/bin/env bash
#
# E2E Test: Build on OpenShift + deploy with Helm
#
# Tests the full workflow:
#   1. Build exporter image on OpenShift
#   2. Install Prometheus and Grafana operators
#   3. Deploy Pelorus via Helm chart
#   4. Tag ImageStreams to use the built image
#   5. Send test metrics via webhook
#   6. Verify metrics in Prometheus and dashboards in Grafana
#   7. Clean up
#
# Usage:
#   ./_test/e2e/test_helm_deploy.sh
#   NAMESPACE=pelorus-test ./_test/e2e/test_helm_deploy.sh
#   SKIP_CLEANUP=1 ./_test/e2e/test_helm_deploy.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

SKIP_CLEANUP="${SKIP_CLEANUP:-0}"

trap '[[ "$SKIP_CLEANUP" == "0" ]] && cleanup' EXIT

log "========================================="
log "E2E Test: Build on OCP + Helm deploy"
log "========================================="

# 1. Setup
create_namespace
install_operators

# 2. Build exporter image (but don't tag imagestreams yet)
log "Building exporter image on OpenShift..."
ln -sf Containerfile exporters/Dockerfile
oc new-build --name=pelorus-exporter --strategy=docker --binary \
  -n "$NAMESPACE" 2>/dev/null || true
oc start-build pelorus-exporter --from-dir=exporters \
  -n "$NAMESPACE" --follow 2>&1 | tail -5
wait_for_build "pelorus-exporter-" 600
pass "Exporter image built"

# 3. Deploy with Helm (creates ImageStreams)
log "Deploying Pelorus via Helm..."
helm install pelorus "$CHART_PATH" -n "$NAMESPACE" \
  --set oauth_proxy_enabled=true \
  --set "exporters.instances[0].app_name=deploytime-exporter" \
  --set "exporters.instances[0].exporter_type=deploytime" \
  --set "exporters.instances[0].image_tag=latest" \
  --set "exporters.instances[1].app_name=committime-exporter" \
  --set "exporters.instances[1].exporter_type=committime" \
  --set "exporters.instances[1].image_tag=latest" \
  --set "exporters.instances[2].app_name=webhook-exporter" \
  --set "exporters.instances[2].exporter_type=webhook" \
  --set "exporters.instances[2].image_tag=latest" \
  --set "exporters.instances[3].app_name=failuretime-exporter" \
  --set "exporters.instances[3].exporter_type=failure" \
  --set "exporters.instances[3].image_tag=latest"

# 4. Tag Helm-managed ImageStreams to use our built image
log "Tagging ImageStreams with built image..."
for t in deploytime committime webhook failuretime; do
  oc tag "pelorus-exporter:latest" "${t}-exporter:stable" -n "$NAMESPACE"
done
pass "ImageStreams tagged"

# 5. Wait for pods (they'll restart with the new image)
sleep 10
wait_for_pods "app.kubernetes.io/name=deploytime-exporter" 1
wait_for_pods "app.kubernetes.io/name=committime-exporter" 1 120
wait_for_pods "app.kubernetes.io/name=webhook-exporter" 1 120
wait_for_pods "prometheus=prometheus-pelorus" 1

# 6. Verify Grafana
wait_for_pods "app=grafana-oauth" 1 180
verify_grafana

# 7. Send test metrics and verify
send_test_metrics
verify_prometheus_metrics

# 8. Verify routes exist
log "Checking routes..."
oc get route -n "$NAMESPACE" --no-headers | while read -r line; do
  name=$(echo "$line" | awk '{print $1}')
  host=$(echo "$line" | awk '{print $2}')
  pass "Route: $name -> $host"
done

log "========================================="
log "E2E Test PASSED: Helm deploy"
log "========================================="
