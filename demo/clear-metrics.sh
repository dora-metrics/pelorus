#!/usr/bin/env bash
#
# Clear Pelorus DORA metrics from Prometheus.
# Deletes all time series for Pelorus metrics to allow fresh seeding.
#
# Requires Prometheus to have the admin API enabled (--web.enable-admin-api).
# The install script enables this automatically for the demo/dev environment.
#
# Usage:
#   ./demo/clear-metrics.sh                          # auto-detect endpoint
#   ./demo/clear-metrics.sh http://localhost:9090     # explicit endpoint
#   PROMETHEUS_URL=http://localhost:9090 ./demo/clear-metrics.sh
#
set -euo pipefail

PROMETHEUS_URL="${1:-${PROMETHEUS_URL:-}}"

if [[ -z "$PROMETHEUS_URL" ]]; then
  if command -v oc &>/dev/null && oc whoami &>/dev/null 2>&1; then
    echo "Starting port-forward to prometheus..."
    oc port-forward -n pelorus svc/prometheus 19090:9090 &>/dev/null &
    PF_PID=$!
    trap "kill $PF_PID 2>/dev/null || true" EXIT
    sleep 2
    PROMETHEUS_URL="http://localhost:19090"
  else
    echo "Usage: $0 <prometheus-url>"
    echo "  e.g. $0 http://localhost:9090"
    exit 1
  fi
fi

echo "Using Prometheus endpoint: $PROMETHEUS_URL"
echo ""

# Pelorus metric names from webhook exporter
METRICS=(
  "commit_timestamp"
  "deploy_timestamp"
  "failure_creation_timestamp"
  "failure_resolution_timestamp"
)

echo "================================================================"
echo "  Clearing Pelorus DORA metrics from Prometheus"
echo "================================================================"
echo ""

# Check if Prometheus is accessible
if ! curl -sf "${PROMETHEUS_URL}/api/v1/status/config" &>/dev/null; then
  echo "ERROR: Prometheus is not accessible at ${PROMETHEUS_URL}"
  exit 1
fi

echo "Prometheus is accessible ✓"

# Test if admin API is actually enabled by trying a simple delete
echo -n "Checking if admin API is enabled... "
test_response=$(curl -s -w "%{http_code}" -o /tmp/curl_test_$$.json -X POST \
  "${PROMETHEUS_URL}/api/v1/admin/tsdb/delete_series" \
  --data-urlencode "match[]={__name__=~\"nonexistent_metric_test\"}" \
  2>&1)
test_body=$(cat /tmp/curl_test_$$.json 2>/dev/null || echo "")
rm -f /tmp/curl_test_$$.json

if echo "$test_body" | grep -q "admin APIs disabled"; then
  echo "DISABLED"
  echo ""
  echo "ERROR: Prometheus admin API is not enabled"
  echo ""
  echo "To enable the admin API, Prometheus must be started with:"
  echo "  --web.enable-admin-api"
  echo ""
  echo "In Kubernetes/OpenShift, you need to add this flag to the Prometheus"
  echo "deployment or StatefulSet. Check the prometheus configuration:"
  echo ""
  echo "  oc get prometheus -n pelorus -o yaml"
  echo "  oc get statefulset -n pelorus prometheus-pelorus -o yaml"
  echo ""
  echo "Look for the 'args' section and add '--web.enable-admin-api'"
  exit 1
fi

echo "✓"
echo ""

# Delete each metric
for metric in "${METRICS[@]}"; do
  echo -n "Deleting ${metric}... "

  # Delete all time series for this metric
  # Use -w to get HTTP status code, capture both stdout and stderr
  http_code=$(curl -s -w "%{http_code}" -o /tmp/curl_response_$$.json -X POST \
    "${PROMETHEUS_URL}/api/v1/admin/tsdb/delete_series" \
    --data-urlencode "match[]=${metric}" \
    2>&1)

  response=$(cat /tmp/curl_response_$$.json 2>/dev/null || echo "")
  rm -f /tmp/curl_response_$$.json

  # Check HTTP status code
  if [[ "$http_code" != "200" ]] && [[ "$http_code" != "204" ]]; then
    echo "FAILED"
    echo "  HTTP Status: $http_code"
    echo "  Response: $response"
    if [[ "$http_code" == "000" ]]; then
      echo "  Hint: Could not connect to Prometheus at $PROMETHEUS_URL"
      echo "        Check that the URL is correct and Prometheus is running"
    elif [[ "$http_code" == "404" ]]; then
      echo "  Hint: Admin API endpoint not found. Ensure Prometheus is started with --web.enable-admin-api"
    fi
    continue
  fi

  # Check if deletion was successful
  if echo "$response" | grep -q '"status":"success"'; then
    echo "✓"
  else
    echo "FAILED"
    echo "  Response: $response"
  fi
done

echo ""
echo -n "Cleaning up tombstones... "

# Clean tombstones to free up disk space
http_code=$(curl -s -w "%{http_code}" -o /tmp/curl_response_$$.json -X POST \
  "${PROMETHEUS_URL}/api/v1/admin/tsdb/clean_tombstones" \
  2>&1)

response=$(cat /tmp/curl_response_$$.json 2>/dev/null || echo "")
rm -f /tmp/curl_response_$$.json

if [[ "$http_code" != "200" ]] && [[ "$http_code" != "204" ]]; then
  echo "FAILED"
  echo "  HTTP Status: $http_code"
  echo "  Response: $response"
  if [[ "$http_code" == "000" ]]; then
    echo "  Hint: Could not connect to Prometheus"
  elif [[ "$http_code" == "404" ]]; then
    echo "  Hint: Admin API not enabled"
  fi
  exit 1
fi

if echo "$response" | grep -q '"status":"success"'; then
  echo "✓"
else
  echo "FAILED"
  echo "  Response: $response"
  exit 1
fi

echo ""
echo "================================================================"
echo "  Done - all Pelorus metrics cleared from Prometheus"
echo "================================================================"
echo ""
echo "You can now run ./demo/seed-metrics.sh to load fresh demo data."
echo "Note: It may take 30-60 seconds for Prometheus to fully scrape"
echo "      and process the new metrics."
echo ""
