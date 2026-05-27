#!/usr/bin/env bash
#
# Clean up Pelorus from OpenShift. Handles stuck finalizers.
#
# Usage:
#   ./demo/cleanup.sh
#
set -euo pipefail

NAMESPACE="${NAMESPACE:-pelorus}"
OPERATOR_NS="${NAMESPACE}-operator-system"

log() { echo "[$(date +%H:%M:%S)] $*"; }

force_delete_ns() {
  local ns="$1"
  oc get ns "$ns" &>/dev/null || return 0

  log "Deleting namespace $ns..."

  # Remove finalizers from Pelorus CRs
  for r in $(oc get grafanadashboard,grafanadatasource,grafana,pelorus -n "$ns" -o name 2>/dev/null); do
    oc patch "$r" -n "$ns" --type=merge -p '{"metadata":{"finalizers":[]}}' 2>/dev/null || true
  done

  oc delete ns "$ns" --force --wait=false 2>/dev/null || true
  sleep 3

  # Force finalize if stuck
  if oc get ns "$ns" &>/dev/null 2>&1; then
    log "Force-finalizing $ns..."
    oc get ns "$ns" -o json 2>/dev/null \
      | python3 -c "import sys,json; ns=json.load(sys.stdin); ns['spec']['finalizers']=[]; print(json.dumps(ns))" \
      | oc replace --raw "/api/v1/namespaces/$ns/finalize" -f - 2>/dev/null || true
  fi

  # Wait for deletion
  local elapsed=0
  while oc get ns "$ns" &>/dev/null 2>&1 && [[ $elapsed -lt 30 ]]; do
    sleep 3
    elapsed=$((elapsed + 3))
  done

  if oc get ns "$ns" &>/dev/null 2>&1; then
    log "WARNING: $ns still exists (may need manual cleanup)"
  else
    log "$ns deleted"
  fi
}

# Clean up ClusterRoleBindings
log "Cleaning up cluster resources..."
oc delete clusterrolebinding pelorus-grafana-cluster-monitoring-view 2>/dev/null || true
oc delete clusterrolebinding pelorus-operator-manager-rolebinding 2>/dev/null || true
oc delete clusterrolebinding pelorus-operator-pelorus-manager-rolebinding 2>/dev/null || true
oc delete clusterrolebinding pelorus-operator-proxy-rolebinding 2>/dev/null || true
oc delete clusterrole pelorus-operator-monitoring-extras 2>/dev/null || true
oc delete clusterrolebinding pelorus-operator-monitoring-extras 2>/dev/null || true
oc delete clusterrole pelorus-grafana 2>/dev/null || true
oc delete clusterrolebinding pelorus-grafana 2>/dev/null || true

# Kill port-forwards
lsof -ti:18080,19090,13000 2>/dev/null | xargs kill 2>/dev/null || true

force_delete_ns "$NAMESPACE"
force_delete_ns "$OPERATOR_NS"

log "Cleanup complete"
