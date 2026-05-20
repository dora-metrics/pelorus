#!/bin/bash
# Cleanup existing Prometheus Operator installation before upgrading to v0.70.0
# This is necessary when switching from community-operators to operatorhubio-catalog

set -e

NAMESPACE="${NAMESPACE:-pelorus}"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

warn() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $*" >&2
}

fail() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
  exit 1
}

log "Prometheus Operator Cleanup Script"
log "This will remove the existing v0.56.3 operator to prepare for v0.70.0 upgrade"
echo

# Check if we're logged in
oc whoami &>/dev/null || fail "Not logged into OpenShift cluster"

# 1. Check if Pelorus CR exists (backup if it does)
log "Checking for Pelorus CR..."
if oc get pelorus -n "$NAMESPACE" &>/dev/null; then
  pelorus_name=$(oc get pelorus -n "$NAMESPACE" -o name | head -1)
  if [[ -n "$pelorus_name" ]]; then
    backup_file="/tmp/pelorus-cr-backup-$(date +%Y%m%d-%H%M%S).yaml"
    log "Backing up Pelorus CR to $backup_file"
    oc get "$pelorus_name" -n "$NAMESPACE" -o yaml > "$backup_file"
    log "✓ Backup saved: $backup_file"

    log "Deleting Pelorus CR (will be recreated by install script)..."
    oc delete "$pelorus_name" -n "$NAMESPACE" --wait=true
    log "✓ Pelorus CR deleted"
  fi
else
  log "No Pelorus CR found"
fi

# 2. Delete Prometheus CR if it exists
log "Checking for Prometheus CR..."
if oc get prometheus prometheus-pelorus -n "$NAMESPACE" &>/dev/null; then
  log "Deleting Prometheus CR prometheus-pelorus..."
  oc delete prometheus prometheus-pelorus -n "$NAMESPACE" --wait=true
  log "✓ Prometheus CR deleted"
else
  log "No Prometheus CR found"
fi

# 3. Delete Prometheus Operator Subscription
log "Checking for Prometheus Operator subscription..."
if oc get subscription prometheus -n "$NAMESPACE" &>/dev/null; then
  log "Deleting Prometheus Operator subscription..."
  oc delete subscription prometheus -n "$NAMESPACE"
  log "✓ Subscription deleted"
else
  log "No Prometheus subscription found"
fi

# 4. Delete Prometheus Operator CSV
log "Checking for Prometheus Operator CSV..."
csv_name=$(oc get csv -n "$NAMESPACE" --no-headers 2>/dev/null | grep prometheusoperator | awk '{print $1}' | head -1)
if [[ -n "$csv_name" ]]; then
  log "Deleting CSV: $csv_name"
  oc delete csv "$csv_name" -n "$NAMESPACE"
  log "✓ CSV deleted"

  # Wait for operator pod to terminate
  log "Waiting for operator pod to terminate..."
  sleep 5

  # Check if any prometheusoperator pods are still running
  if oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -q prometheus-operator; then
    warn "Prometheus operator pods still running, waiting..."
    sleep 10
  fi
else
  log "No Prometheus Operator CSV found"
fi

# 5. Verify cleanup
log ""
log "Verifying cleanup..."
remaining_resources=0

if oc get subscription prometheus -n "$NAMESPACE" &>/dev/null; then
  warn "Subscription still exists"
  remaining_resources=$((remaining_resources + 1))
fi

if oc get csv -n "$NAMESPACE" --no-headers 2>/dev/null | grep -q prometheusoperator; then
  warn "CSV still exists"
  remaining_resources=$((remaining_resources + 1))
fi

if oc get prometheus prometheus-pelorus -n "$NAMESPACE" &>/dev/null; then
  warn "Prometheus CR still exists"
  remaining_resources=$((remaining_resources + 1))
fi

if [[ $remaining_resources -eq 0 ]]; then
  log "✓ Cleanup complete!"
  log ""
  log "Next steps:"
  log "  1. Run: ./demo/install.sh"
  log "  2. The script will install Prometheus Operator v0.70.0 from operatorhubio-catalog"
  log "  3. Verify: oc get csv -n pelorus | grep prometheus"
  log "           (should show: prometheusoperator.v0.70.0)"
else
  warn "Some resources still remain. You may need to delete them manually."
  warn "Run 'oc get subscription,csv,prometheus -n $NAMESPACE' to check"
fi

log ""
log "Note: Grafana operator and other components are preserved"
