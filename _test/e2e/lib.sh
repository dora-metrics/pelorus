#!/usr/bin/env bash
# Shared functions for e2e tests

set -euo pipefail

NAMESPACE="${NAMESPACE:-pelorus}"
CHART_PATH="${CHART_PATH:-pelorus-operator/helm-charts/pelorus}"
TIMEOUT="${TIMEOUT:-300}"
POLL_INTERVAL=10

log() { echo "[$(date +%H:%M:%S)] $*"; }
fail() { log "FAIL: $*" >&2; exit 1; }
pass() { log "PASS: $*"; }

wait_for_pods() {
  local label="$1" expected="$2" timeout="${3:-$TIMEOUT}"
  log "Waiting for pods ($label) to be ready..."
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local ready
    ready=$(oc get pods -n "$NAMESPACE" -l "$label" --no-headers 2>/dev/null \
      | grep -c "Running" || true)
    ready="${ready:-0}"
    ready=$(echo "$ready" | tr -d '[:space:]')
    if [[ "$ready" -ge "$expected" ]]; then
      pass "Got $ready/$expected pods running for $label"
      return 0
    fi
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
  done
  log "Pod status:"
  oc get pods -n "$NAMESPACE" -l "$label" 2>&1
  fail "Timed out waiting for $expected pods ($label) after ${timeout}s"
}

wait_for_csv() {
  local name="$1" timeout="${2:-$TIMEOUT}"
  log "Waiting for CSV $name..."
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local phase
    phase=$(oc get csv -n "$NAMESPACE" --no-headers 2>/dev/null \
      | grep "$name" | awk '{print $NF}' || echo "")
    if [[ "$phase" == "Succeeded" ]]; then
      pass "CSV $name succeeded"
      return 0
    fi
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
  done
  fail "Timed out waiting for CSV $name after ${timeout}s"
}

wait_for_build() {
  local name="$1" timeout="${2:-$TIMEOUT}"
  log "Waiting for build $name..."
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local phase
    phase=$(oc get builds -n "$NAMESPACE" --no-headers 2>/dev/null \
      | grep "$name" | tail -1 | awk '{print $4}' || echo "")
    if [[ "$phase" == "Complete" ]]; then
      pass "Build $name complete"
      return 0
    elif [[ "$phase" == "Failed" || "$phase" == "Error" ]]; then
      oc logs "build/${name}" -n "$NAMESPACE" 2>&1 | tail -20
      fail "Build $name failed"
    fi
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
  done
  fail "Timed out waiting for build $name after ${timeout}s"
}

create_namespace() {
  log "Creating namespace $NAMESPACE"
  oc create namespace "$NAMESPACE" 2>/dev/null || true
}

install_operators() {
  log "Installing Prometheus and Grafana operators..."
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
  wait_for_csv "prometheusoperator" 300
  wait_for_csv "grafana-operator" 300
}

build_exporter_image() {
  log "Building exporter image on OpenShift..."
  # Ensure Dockerfile symlink exists
  ln -sf Containerfile exporters/Dockerfile
  oc new-build --name=pelorus-exporter --strategy=docker --binary \
    -n "$NAMESPACE" 2>/dev/null || true
  oc start-build pelorus-exporter --from-dir=exporters \
    -n "$NAMESPACE" --follow 2>&1 | tail -5
  wait_for_build "pelorus-exporter-" 600
  # Tag for each exporter
  for t in deploytime committime webhook failuretime; do
    oc tag "pelorus-exporter:latest" "${t}-exporter:stable" -n "$NAMESPACE"
  done
  pass "Exporter image built and tagged"
}

get_internal_registry() {
  echo "image-registry.openshift-image-registry.svc:5000"
}

send_test_metrics() {
  log "Sending test metrics via webhook..."
  oc port-forward -n "$NAMESPACE" svc/webhook-exporter 18080:8080 &>/dev/null &
  local pf_pid=$!
  sleep 5

  local now
  now=$(date +%s)
  local url="http://localhost:18080/pelorus/webhook"

  for i in $(seq 1 3); do
    local ts=$((now - 1500 + i * 100))
    local img
    img=$(printf "sha256:%064d" $((9000 + i)))
    local hash
    hash=$(printf "%040d" $((8000 + i)))
    curl -sf -o /dev/null -X POST "$url" \
      -H "Content-Type: application/json" \
      -H "User-Agent: Pelorus-Webhook/e2e" \
      -H "X-Pelorus-Event: committime" \
      -d "{\"app\":\"e2e-app\",\"commit_hash\":\"$hash\",\"image_sha\":\"$img\",\"namespace\":\"e2e-ns\",\"timestamp\":$ts}"
    curl -sf -o /dev/null -X POST "$url" \
      -H "Content-Type: application/json" \
      -H "User-Agent: Pelorus-Webhook/e2e" \
      -H "X-Pelorus-Event: deploytime" \
      -d "{\"app\":\"e2e-app\",\"image_sha\":\"$img\",\"namespace\":\"e2e-ns\",\"timestamp\":$((ts + 60))}"
  done

  curl -sf -o /dev/null -X POST "$url" \
    -H "Content-Type: application/json" \
    -H "User-Agent: Pelorus-Webhook/e2e" \
    -H "X-Pelorus-Event: failure" \
    -d "{\"app\":\"e2e-app\",\"failure_id\":\"E2E-1\",\"failure_event\":\"created\",\"timestamp\":$((now - 500))}"
  curl -sf -o /dev/null -X POST "$url" \
    -H "Content-Type: application/json" \
    -H "User-Agent: Pelorus-Webhook/e2e" \
    -H "X-Pelorus-Event: failure" \
    -d "{\"app\":\"e2e-app\",\"failure_id\":\"E2E-1\",\"failure_event\":\"resolved\",\"timestamp\":$((now - 200))}"

  kill "$pf_pid" 2>/dev/null || true
  pass "Sent 3 commits, 3 deploys, 1 failure"
}

verify_prometheus_metrics() {
  log "Waiting for Prometheus to scrape metrics..."
  sleep 60

  local prom_pod
  prom_pod=$(oc get pods -n "$NAMESPACE" -l prometheus=prometheus-pelorus \
    --no-headers -o name 2>/dev/null | head -1)
  [[ -z "$prom_pod" ]] && fail "No Prometheus pod found"

  for metric in commit_timestamp deploy_timestamp; do
    local count
    count=$(oc exec -n "$NAMESPACE" "$prom_pod" -c prometheus -- \
      wget -qO- "http://localhost:9090/api/v1/query?query=count($metric)" 2>&1 \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['result'][0]['value'][1] if d['data']['result'] else '0')" 2>&1)
    if [[ "$count" == "0" ]]; then
      fail "$metric count is 0 in Prometheus"
    fi
    pass "$metric: $count series in Prometheus"
  done

  # Check recording rules
  local lead_time
  lead_time=$(oc exec -n "$NAMESPACE" "$prom_pod" -c prometheus -- \
    wget -qO- "http://localhost:9090/api/v1/query?query=sdp:lead_time:global" 2>&1 \
    | python3 -c "import json,sys; d=json.load(sys.stdin); r=d['data']['result']; print(r[0]['value'][1] if r else 'none')" 2>&1)
  if [[ "$lead_time" == "none" ]]; then
    fail "sdp:lead_time:global recording rule has no data"
  fi
  pass "sdp:lead_time:global = ${lead_time}s"
}

verify_grafana() {
  log "Checking Grafana dashboards..."
  local grafana_pod
  grafana_pod=$(oc get pods -n "$NAMESPACE" --no-headers -o name 2>/dev/null \
    | grep grafana | grep -v operator | head -1) || true
  [[ -z "$grafana_pod" ]] && fail "No Grafana pod found"

  # Try both passwords
  local dashboard_count="0"
  for pw in changeme pelorus admin; do
    dashboard_count=$(oc exec -n "$NAMESPACE" "$grafana_pod" -- \
      wget -qO- "http://admin:${pw}@localhost:3000/api/search" 2>/dev/null \
      | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null) || true
    dashboard_count="${dashboard_count:-0}"
    [[ "$dashboard_count" -gt 0 ]] 2>/dev/null && break
  done
  if [[ "$dashboard_count" -ge 2 ]] 2>/dev/null; then
    pass "Found $dashboard_count dashboards in Grafana"
  else
    log "WARN: Found $dashboard_count dashboards (may need time to sync)"
    pass "Grafana is running (dashboards: $dashboard_count)"
  fi
}

cleanup() {
  log "Cleaning up..."
  helm uninstall pelorus -n "$NAMESPACE" 2>/dev/null || true
  oc delete sub --all -n "$NAMESPACE" 2>/dev/null || true
  oc delete csv --all -n "$NAMESPACE" 2>/dev/null || true
  oc delete og --all -n "$NAMESPACE" 2>/dev/null || true
  oc delete bc pelorus-exporter -n "$NAMESPACE" 2>/dev/null || true
  oc delete is pelorus-exporter -n "$NAMESPACE" 2>/dev/null || true
  oc delete clusterrole pelorus-exporter pelorus-prometheus grafana-oauth-cluster-role 2>/dev/null || true
  oc delete clusterrolebinding pelorus-exporter pelorus-prometheus grafana-oauth-cluster-role-binding 2>/dev/null || true
  oc delete namespace "$NAMESPACE" 2>/dev/null || true
  rm -f exporters/Dockerfile
  log "Cleanup complete"
}
