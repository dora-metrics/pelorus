#!/usr/bin/env bash
#
# Pelorus Live Demo - Simple version
#
# Deploys a real app on OpenShift, triggers builds and deploys,
# and shows Pelorus capturing DORA metrics automatically.
# No Tekton required - uses oc new-app and oc start-build.
#
# Prerequisites:
#   - Pelorus deployed (via Helm or Operator)
#   - oc logged in as admin
#
# Usage:
#   ./demo/live-demo.sh                    # interactive
#   AUTO=1 ./demo/live-demo.sh             # non-interactive
#   APP_GIT_URL=https://github.com/myorg/pelorus.git ./demo/live-demo.sh
#
set -euo pipefail

AUTO="${AUTO:-0}"
NAMESPACE="${NAMESPACE:-pelorus}"
APP_NAME="demo-python-app"
APP_NS="${APP_NAME}"
APP_GIT_URL="${APP_GIT_URL:-https://github.com/dora-metrics/pelorus.git}"
APP_GIT_REF="${APP_GIT_REF:-main}"
APP_CONTEXT="demo/python-example"

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
    sleep 3
  fi
}

next_step() {
  step=$((step + 1))
  banner "Step $step: $1"
}

cleanup() {
  echo ""
  info "Cleaning up demo app..."
  oc delete project "$APP_NS" 2>/dev/null || true
}

trap cleanup EXIT

# ---------------------------------------------------------------------------
banner "Pelorus Live Demo"
echo "  This demo deploys a real application and shows Pelorus"
echo "  capturing DORA metrics automatically - zero instrumentation."
echo ""
echo "  App:     $APP_NAME"
echo "  Source:  $APP_GIT_URL ($APP_GIT_REF)"
echo "  Cluster: $(oc whoami --show-server 2>/dev/null)"
pause

# ---------------------------------------------------------------------------
next_step "Deploy a sample application"

info "Creating project '$APP_NS'..."
oc new-project "$APP_NS" 2>/dev/null || oc project "$APP_NS"

info "Building the app from source (S2I)..."
echo ""
echo -e "  ${BOLD}oc new-app python~${APP_GIT_URL}#${APP_GIT_REF}${NC}"
echo -e "  ${BOLD}  --context-dir=${APP_CONTEXT} --name=${APP_NAME}${NC}"
echo ""

oc new-app "python~${APP_GIT_URL}#${APP_GIT_REF}" \
  --context-dir="$APP_CONTEXT" \
  --name="$APP_NAME" \
  -l "app.kubernetes.io/name=${APP_NAME}" \
  -n "$APP_NS" 2>&1 | grep -E -- "-->|imagestream|build|deployment|service|Creating" || true

info "Exposing the route..."
oc expose svc/"$APP_NAME" -n "$APP_NS" 2>/dev/null || true

info "Waiting for build to complete..."
oc logs -f "bc/${APP_NAME}" -n "$APP_NS" 2>&1 | tail -5

info "Waiting for deployment..."
oc rollout status "deployment/${APP_NAME}" -n "$APP_NS" --timeout=120s 2>/dev/null || \
  oc rollout status "dc/${APP_NAME}" -n "$APP_NS" --timeout=120s 2>/dev/null || true

APP_URL=$(oc get route "$APP_NAME" -n "$APP_NS" -o jsonpath='{.spec.host}' 2>/dev/null)
echo ""
info "App is live at: http://${APP_URL}"
curl -sf "http://${APP_URL}" 2>/dev/null && echo "" || warn "App not responding yet (may need a moment)"

pause

# ---------------------------------------------------------------------------
next_step "See Pelorus capture the deployment"

info "The deploytime-exporter detected the new pod automatically."
info "The committime-exporter found the git commit via the build metadata."
echo ""
info "Checking deploytime-exporter metrics..."

# Give exporters a scrape cycle
sleep 15

# Port-forward to check metrics directly
oc port-forward -n "$NAMESPACE" svc/deploytime-exporter 18081:8080 &>/dev/null &
PF1=$!
sleep 2

DEPLOY_METRICS=$(curl -sf http://localhost:18081/metrics 2>/dev/null | grep "deploy_timestamp.*${APP_NAME}" | head -3 || true)
kill "$PF1" 2>/dev/null || true

if [[ -n "$DEPLOY_METRICS" ]]; then
  info "deploytime-exporter found the deployment:"
  echo "$DEPLOY_METRICS" | while read -r line; do
    echo -e "    ${GREEN}$line${NC}"
  done
else
  warn "Deployment not detected yet - the exporter scrapes every 30s."
  warn "In the Grafana dashboard, data will appear after the next scrape cycle."
fi

echo ""
info "Checking committime-exporter metrics..."
oc port-forward -n "$NAMESPACE" svc/committime-exporter 18082:8080 &>/dev/null &
PF2=$!
sleep 2

COMMIT_METRICS=$(curl -sf http://localhost:18082/metrics 2>/dev/null | grep "commit_timestamp.*${APP_NAME}" | head -3 || true)
kill "$PF2" 2>/dev/null || true

if [[ -n "$COMMIT_METRICS" ]]; then
  info "committime-exporter found the commit:"
  echo "$COMMIT_METRICS" | while read -r line; do
    echo -e "    ${GREEN}$line${NC}"
  done
else
  warn "Commit not detected yet - the exporter needs to query the git provider."
  warn "Make sure GIT_TOKEN is configured in the committime-exporter."
fi

pause

# ---------------------------------------------------------------------------
next_step "Make a change and redeploy"

info "Modifying the application and triggering a new build..."
info "This simulates a developer pushing a code change."
echo ""

# Trigger a new build (rebuilds from the same source)
oc start-build "$APP_NAME" -n "$APP_NS" --follow 2>&1 | tail -5

info "New build complete. Waiting for rollout..."
sleep 10

info "Pelorus will capture this as a second deployment."
info "The lead time is the gap between the git commit and this deployment."
echo ""
info "In Grafana, you'll now see:"
echo "    - Deployment Frequency: 2 deploys"
echo "    - Lead Time: time from commit to each deploy"

pause

# ---------------------------------------------------------------------------
next_step "Simulate an incident"

info "Sending a failure event via the webhook exporter..."
info "In production, this would come from Jira, ServiceNow, or PagerDuty."
echo ""

oc port-forward -n "$NAMESPACE" svc/webhook-exporter 18080:8080 &>/dev/null &
PF3=$!
sleep 2

NOW=$(date +%s)
FAIL_ID="INC-DEMO-${NOW}"

curl -sf -o /dev/null -X POST http://localhost:18080/pelorus/webhook \
  -H "Content-Type: application/json" \
  -H "User-Agent: Pelorus-Webhook/demo" \
  -H "X-Pelorus-Event: failure" \
  -d "{\"app\":\"${APP_NAME}\",\"failure_id\":\"${FAIL_ID}\",\"failure_event\":\"created\",\"timestamp\":${NOW}}"

info "Incident ${FAIL_ID} created. The clock is ticking..."
echo ""

if [[ "$AUTO" == "0" ]]; then
  echo -e "  ${YELLOW}(Wait a moment to simulate incident response time, then press ENTER)${NC}"
  read -r
else
  sleep 10
fi

RESOLVE_TS=$(date +%s)
MTTR=$((RESOLVE_TS - NOW))

curl -sf -o /dev/null -X POST http://localhost:18080/pelorus/webhook \
  -H "Content-Type: application/json" \
  -H "User-Agent: Pelorus-Webhook/demo" \
  -H "X-Pelorus-Event: failure" \
  -d "{\"app\":\"${APP_NAME}\",\"failure_id\":\"${FAIL_ID}\",\"failure_event\":\"resolved\",\"timestamp\":${RESOLVE_TS}}"

kill "$PF3" 2>/dev/null || true

info "Incident resolved. Mean Time to Restore: ${MTTR} seconds."
echo ""
info "Pelorus now has all 4 DORA metrics for ${APP_NAME}:"
echo "    1. Lead Time for Change  - from the git commit to deployment"
echo "    2. Deployment Frequency  - 2 deploys captured"
echo "    3. Mean Time to Restore  - ${MTTR}s for this incident"
echo "    4. Change Failure Rate   - 1 failure / 2 deploys = 50%"

pause

# ---------------------------------------------------------------------------
next_step "View the dashboards"

GRAFANA_ROUTE=$(oc get route -n "$NAMESPACE" -o jsonpath='{.items[0].spec.host}' 2>/dev/null || echo "grafana-pelorus.apps-crc.testing")

echo ""
info "Open Grafana in your browser:"
echo ""
echo -e "    ${BOLD}https://${GRAFANA_ROUTE}${NC}"
echo ""
info "Navigate to:"
echo "    Dashboards > Pelorus > Software Delivery Performance"
echo "    Dashboards > Pelorus > Software Delivery Performance - By App"
echo ""
info "Set time range to 'Last 30 minutes'"
echo ""
info "You should see '${APP_NAME}' alongside the other seeded applications,"
info "with real metrics from the build and deployment you just triggered."

pause

# ---------------------------------------------------------------------------
banner "Demo Complete"
echo ""
echo "  What happened:"
echo "    - Built a real app from source using S2I on OpenShift"
echo "    - Pelorus detected the deployment and git commit automatically"
echo "    - Rebuilt and redeployed to show deployment frequency"
echo "    - Simulated an incident to capture MTTR and change failure rate"
echo "    - All 4 DORA metrics visible in Grafana - zero app instrumentation"
echo ""
echo "  The demo app will be cleaned up automatically."
echo ""
