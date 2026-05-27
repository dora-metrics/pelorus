#!/usr/bin/env bash
#
# Pelorus Interactive Demo
#
# Step-by-step walkthrough that builds, deploys, and demonstrates
# Pelorus DORA metrics on OpenShift. Pauses between steps so you
# can explain what's happening during a live demo.
#
# Usage:
#   ./demo/run-demo.sh              # interactive (pauses between steps)
#   AUTO=1 ./demo/run-demo.sh       # non-interactive (no pauses)
#   SKIP_BUILD=1 ./demo/run-demo.sh # skip image build (reuse existing)
#
set -euo pipefail

NAMESPACE="${NAMESPACE:-pelorus}"
CHART_PATH="${CHART_PATH:-pelorus-operator/helm-charts/pelorus}"
AUTO="${AUTO:-0}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

step=0

banner() {
  echo ""
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  $*${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

info() { echo -e "  ${GREEN}$*${NC}"; }
warn() { echo -e "  ${YELLOW}$*${NC}"; }

pause() {
  if [[ "$AUTO" == "0" ]]; then
    echo ""
    echo -e "  ${YELLOW}Press ENTER to continue...${NC}"
    read -r
  else
    sleep 2
  fi
}

next_step() {
  step=$((step + 1))
  banner "Step $step: $1"
}

# ---------------------------------------------------------------------------
banner "Pelorus DORA Metrics Demo"
echo "  This demo will:"
echo "    1. Build the Pelorus exporter image on OpenShift"
echo "    2. Install Prometheus and Grafana operators"
echo "    3. Deploy Pelorus via Helm"
echo "    4. Simulate application deployments and incidents"
echo "    5. Show DORA metrics in Prometheus and Grafana"
echo ""
echo "  Cluster: $(oc whoami --show-server 2>/dev/null || echo 'not logged in')"
echo "  User:    $(oc whoami 2>/dev/null || echo 'not logged in')"
pause

# ---------------------------------------------------------------------------
next_step "Create namespace and install operators"

info "Creating namespace '$NAMESPACE'..."
oc create namespace "$NAMESPACE" 2>/dev/null || info "Namespace already exists"

info "Installing Prometheus Operator and Grafana Operator from OperatorHub..."
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

info "Waiting for operators to be ready..."
for i in $(seq 1 30); do
  count=$(oc get csv -n "$NAMESPACE" --no-headers 2>/dev/null | grep -c "Succeeded" || true)
  [[ "${count:-0}" -ge 2 ]] && break
  sleep 10
done
info "Operators installed:"
oc get csv -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{printf "    %-40s %s\n", $1, $NF}'

pause

# ---------------------------------------------------------------------------
if [[ "$SKIP_BUILD" == "0" ]]; then
  next_step "Build the exporter image on OpenShift"

  info "All Pelorus exporters share one image."
  info "The APP_FILE env var selects which exporter runs."
  echo ""
  info "Starting binary build from exporters/Containerfile..."

  ln -sf Containerfile exporters/Dockerfile
  oc new-build --name=pelorus-exporter --strategy=docker --binary \
    -n "$NAMESPACE" 2>/dev/null || info "BuildConfig already exists"
  oc start-build pelorus-exporter --from-dir=exporters \
    -n "$NAMESPACE" --follow 2>&1 | tail -5

  info "Build complete. Image pushed to internal registry."
  pause
else
  info "Skipping build (SKIP_BUILD=1)"
fi

# ---------------------------------------------------------------------------
next_step "Deploy Pelorus with Helm"

info "Installing the Pelorus Helm chart..."
info "This creates: 4 exporters, Prometheus, Grafana, dashboards, recording rules"
echo ""

helm upgrade --install pelorus "$CHART_PATH" -n "$NAMESPACE" \
  --set oauth_proxy_enabled=false \
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
  --set "exporters.instances[3].image_tag=latest" \
  2>&1 | tail -5

# Tag ImageStreams with our built image
if [[ "$SKIP_BUILD" == "0" ]]; then
  info "Tagging ImageStreams with built image..."
  for t in deploytime committime webhook failuretime; do
    oc tag "pelorus-exporter:latest" "${t}-exporter:stable" -n "$NAMESPACE" 2>/dev/null || true
  done
fi

info "Waiting for pods..."
sleep 20

echo ""
info "Pod status:"
oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | \
  grep -v "build\|operator" | \
  awk '{printf "    %-50s %s\n", $1, $3}'

pause

# ---------------------------------------------------------------------------
next_step "Verify the monitoring stack"

info "Checking Prometheus targets..."
sleep 10
PROM_POD=$(oc get pods -n "$NAMESPACE" -l prometheus=prometheus-pelorus \
  --no-headers -o name 2>/dev/null | head -1)

if [[ -n "$PROM_POD" ]]; then
  oc exec -n "$NAMESPACE" "$PROM_POD" -c prometheus -- \
    wget -qO- "http://localhost:9090/api/v1/targets" 2>&1 | \
    python3 -c "
import json,sys
d=json.load(sys.stdin)
for t in d['data']['activeTargets']:
    health = '\033[0;32mUP\033[0m' if t['health']=='up' else '\033[0;31mDOWN\033[0m'
    print(f\"    {t['labels'].get('job','?'):30s} {health}\")
" 2>/dev/null || warn "Prometheus not ready yet"
fi

echo ""
info "Grafana dashboard URL:"
GRAFANA_ROUTE=$(oc get route -n "$NAMESPACE" -o jsonpath='{.items[0].spec.host}' 2>/dev/null || echo "pending")
info "    https://$GRAFANA_ROUTE"
info "    Login: admin / \${PELORUS_PASSWORD:-changeme}"

pause

# ---------------------------------------------------------------------------
next_step "Simulate application deployments"

info "Sending DORA metrics for 4 applications via the webhook exporter."
info "This simulates real commit, deploy, and incident data."
echo ""

# Port-forward to webhook
oc port-forward -n "$NAMESPACE" svc/webhook-exporter 18080:8080 &>/dev/null &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null || true" EXIT
sleep 3

WEBHOOK="http://localhost:18080/pelorus/webhook"
NOW=$(date +%s)
SEQ=5000

send() {
  curl -sf -o /dev/null -X POST "$WEBHOOK" \
    -H "Content-Type: application/json" \
    -H "User-Agent: Pelorus-Webhook/demo" \
    -H "X-Pelorus-Event: $1" \
    -d "$2"
}

# --- frontend: Elite performer ---
info "frontend (Elite) - 6 deploys, fast lead times, 1 incident"
for i in $(seq 1 6); do
  SEQ=$((SEQ + 1))
  ts=$((NOW - 1600 + i * 100))
  img=$(printf "sha256:%064d" $SEQ)
  hash=$(printf "%040d" $SEQ)
  lt=$((20 + i * 5))
  send committime "{\"app\":\"frontend\",\"commit_hash\":\"$hash\",\"image_sha\":\"$img\",\"namespace\":\"frontend-prod\",\"timestamp\":$ts}"
  send deploytime "{\"app\":\"frontend\",\"image_sha\":\"$img\",\"namespace\":\"frontend-prod\",\"timestamp\":$((ts + lt))}"
done
send failure "{\"app\":\"frontend\",\"failure_id\":\"FRONT-1\",\"failure_event\":\"created\",\"timestamp\":$((NOW - 400))}"
send failure "{\"app\":\"frontend\",\"failure_id\":\"FRONT-1\",\"failure_event\":\"resolved\",\"timestamp\":$((NOW - 200))}"
echo -e "    ${GREEN}6 deploys  |  avg lead time: ~40s  |  1 incident (MTTR: 200s)${NC}"

# --- api-gateway: Medium performer ---
info "api-gateway (Medium) - 4 deploys, moderate lead times, 2 incidents"
for i in $(seq 1 4); do
  SEQ=$((SEQ + 1))
  ts=$((NOW - 1600 + i * 150))
  img=$(printf "sha256:%064d" $SEQ)
  hash=$(printf "%040d" $SEQ)
  lt=$((150 + i * 40))
  send committime "{\"app\":\"api-gateway\",\"commit_hash\":\"$hash\",\"image_sha\":\"$img\",\"namespace\":\"api-prod\",\"timestamp\":$ts}"
  send deploytime "{\"app\":\"api-gateway\",\"image_sha\":\"$img\",\"namespace\":\"api-prod\",\"timestamp\":$((ts + lt))}"
done
send failure "{\"app\":\"api-gateway\",\"failure_id\":\"API-1\",\"failure_event\":\"created\",\"timestamp\":$((NOW - 800))}"
send failure "{\"app\":\"api-gateway\",\"failure_id\":\"API-1\",\"failure_event\":\"resolved\",\"timestamp\":$((NOW - 300))}"
send failure "{\"app\":\"api-gateway\",\"failure_id\":\"API-2\",\"failure_event\":\"created\",\"timestamp\":$((NOW - 500))}"
send failure "{\"app\":\"api-gateway\",\"failure_id\":\"API-2\",\"failure_event\":\"resolved\",\"timestamp\":$((NOW - 250))}"
echo -e "    ${GREEN}4 deploys  |  avg lead time: ~230s |  2 incidents (MTTR: 375s)${NC}"

# --- payment-service: Low performer ---
info "payment-service (Low) - 2 deploys, slow lead times, 2 incidents (1 open)"
for i in $(seq 1 2); do
  SEQ=$((SEQ + 1))
  ts=$((NOW - 1600 + i * 200))
  img=$(printf "sha256:%064d" $SEQ)
  hash=$(printf "%040d" $SEQ)
  lt=$((600 + i * 150))
  send committime "{\"app\":\"payment-service\",\"commit_hash\":\"$hash\",\"image_sha\":\"$img\",\"namespace\":\"payments-prod\",\"timestamp\":$ts}"
  send deploytime "{\"app\":\"payment-service\",\"image_sha\":\"$img\",\"namespace\":\"payments-prod\",\"timestamp\":$((ts + lt))}"
done
send failure "{\"app\":\"payment-service\",\"failure_id\":\"PAY-1\",\"failure_event\":\"created\",\"timestamp\":$((NOW - 600))}"
send failure "{\"app\":\"payment-service\",\"failure_id\":\"PAY-1\",\"failure_event\":\"resolved\",\"timestamp\":$((NOW - 100))}"
send failure "{\"app\":\"payment-service\",\"failure_id\":\"PAY-2\",\"failure_event\":\"created\",\"timestamp\":$((NOW - 300))}"
echo -e "    ${YELLOW}2 deploys  |  avg lead time: ~825s |  2 incidents (1 OPEN)${NC}"

# --- inventory-service: Improving ---
info "inventory-service (Improving) - 3 deploys, getting faster"
for i in $(seq 1 3); do
  SEQ=$((SEQ + 1))
  ts=$((NOW - 1600 + i * 180))
  img=$(printf "sha256:%064d" $SEQ)
  hash=$(printf "%040d" $SEQ)
  lt=$((400 - i * 80))
  send committime "{\"app\":\"inventory-service\",\"commit_hash\":\"$hash\",\"image_sha\":\"$img\",\"namespace\":\"inventory-prod\",\"timestamp\":$ts}"
  send deploytime "{\"app\":\"inventory-service\",\"image_sha\":\"$img\",\"namespace\":\"inventory-prod\",\"timestamp\":$((ts + lt))}"
done
echo -e "    ${GREEN}3 deploys  |  avg lead time: ~240s |  0 incidents${NC}"

kill "$PF_PID" 2>/dev/null || true

echo ""
info "Total: 15 deploys, 5 incidents across 4 applications"

pause

# ---------------------------------------------------------------------------
next_step "View DORA metrics in Prometheus"

info "Waiting for Prometheus to scrape and evaluate recording rules (60s)..."
sleep 60

echo ""
PROM_POD=$(oc get pods -n "$NAMESPACE" -l prometheus=prometheus-pelorus \
  --no-headers -o name 2>/dev/null | head -1)

query() {
  oc exec -n "$NAMESPACE" "$PROM_POD" -c prometheus -- \
    wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>&1
}

info "Raw metric counts:"
for m in commit_timestamp deploy_timestamp failure_creation_timestamp failure_resolution_timestamp; do
  count=$(query "count($m)" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['result'][0]['value'][1] if d['data']['result'] else '0')" 2>/dev/null || echo "?")
  printf "    %-35s %s\n" "$m" "$count"
done

echo ""
info "DORA Recording Rules:"

lead_global=$(query "sdp:lead_time:global" | python3 -c "import json,sys; d=json.load(sys.stdin); r=d['data']['result']; print(f\"{float(r[0]['value'][1]):.0f}s\") if r else print('n/a')" 2>/dev/null)
printf "    %-35s %s\n" "Lead Time for Change (global)" "$lead_global"

ttr_global=$(query "sdp:time_to_restore:global" | python3 -c "import json,sys; d=json.load(sys.stdin); r=d['data']['result']; print(f\"{float(r[0]['value'][1]):.0f}s\") if r else print('n/a')" 2>/dev/null)
printf "    %-35s %s\n" "Mean Time to Restore (global)" "$ttr_global"

cfr_global=$(query "sdp:change_failure_rate:global" | python3 -c "import json,sys; d=json.load(sys.stdin); r=d['data']['result']; print(f\"{float(r[0]['value'][1])*100:.0f}%%\") if r else print('n/a')" 2>/dev/null)
printf "    %-35s %s\n" "Change Failure Rate (global)" "$cfr_global"

deploy_count=$(query "count(deploy_timestamp)" | python3 -c "import json,sys; d=json.load(sys.stdin); r=d['data']['result']; print(r[0]['value'][1]) if r else print('n/a')" 2>/dev/null)
printf "    %-35s %s\n" "Deployment Frequency (total)" "$deploy_count deploys"

echo ""
info "Per-application Lead Time:"
query "sdp:lead_time:by_app" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for r in sorted(d['data']['result'], key=lambda x: float(x['value'][1])):
    app = r['metric']['app'].strip('/')
    val = float(r['value'][1])
    bar = '#' * min(int(val / 20), 40)
    print(f\"    {app:25s} {val:>8.0f}s  {bar}\")
" 2>/dev/null || warn "No data yet"

pause

# ---------------------------------------------------------------------------
next_step "View dashboards in Grafana"

echo ""
info "Open Grafana in your browser:"
echo ""
echo -e "    ${BOLD}https://$GRAFANA_ROUTE${NC}"
echo ""
info "Login: admin / \${PELORUS_PASSWORD:-changeme}"
echo ""
info "Navigate to:"
echo "    1. Dashboards > Pelorus > Software Delivery Performance"
echo "       Shows the 4 DORA metrics globally"
echo ""
echo "    2. Dashboards > Pelorus > Software Delivery Performance - By App"
echo "       Filter by application to compare performers"
echo ""
info "Set time range to 'Last 30 minutes' for best results."

pause

# ---------------------------------------------------------------------------
banner "Demo Complete"
echo ""
echo "  What you saw:"
echo "    - Pelorus built and deployed on OpenShift via Helm"
echo "    - 4 applications with different performance profiles"
echo "    - All 4 DORA metrics computed via Prometheus recording rules"
echo "    - Grafana dashboards showing Lead Time, Deploy Frequency,"
echo "      MTTR, and Change Failure Rate"
echo ""
echo "  Next steps:"
echo "    - Connect real git providers (GitHub, GitLab, Bitbucket)"
echo "    - Connect issue trackers (Jira, ServiceNow, PagerDuty)"
echo "    - Deploy the Pelorus Operator for GitOps management"
echo ""
echo "  Cleanup:"
echo "    helm uninstall pelorus -n $NAMESPACE"
echo "    oc delete namespace $NAMESPACE"
echo ""
