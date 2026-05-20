#!/usr/bin/env bash
#
# Seed Pelorus with realistic DORA metrics using Prometheus backfill.
# Creates 6 months of project history for 4 teams with different
# performance profiles, improvement arcs, and incident patterns.
#
# This script generates metrics in OpenMetrics format and uses Prometheus's
# backfill feature to import them directly into the TSDB. This is ideal for
# demo/dev scenarios where you want historical data without real-time ingestion.
#
# Requirements:
# - Prometheus must be running with admin API enabled
# - Prometheus MUST have persistent storage enabled (prometheus_storage: true)
#   Otherwise backfilled data will be lost on pod restart
# - Sufficient disk space for 6 months of metrics (~100MB)
#
# Usage:
#   ./demo/seed-metrics.sh                    # auto-detect namespace
#   NAMESPACE=pelorus ./demo/seed-metrics.sh  # explicit namespace
#
set -euo pipefail

NAMESPACE="${NAMESPACE:-pelorus}"
PROMETHEUS_POD=""
METRICS_FILE="/tmp/pelorus-seed-metrics.txt"

log() { echo "[$(date +%H:%M:%S)] $*"; }
fail() { log "FAIL: $*" >&2; exit 1; }

# Find Prometheus pod
find_prometheus_pod() {
  PROMETHEUS_POD=$(oc get pods -n "$NAMESPACE" -l app.kubernetes.io/name=prometheus \
    --field-selector=status.phase=Running -o name 2>/dev/null | head -1)

  if [[ -z "$PROMETHEUS_POD" ]]; then
    fail "No running Prometheus pod found in namespace $NAMESPACE"
  fi

  # Strip "pod/" prefix
  PROMETHEUS_POD=${PROMETHEUS_POD#pod/}
  log "Found Prometheus pod: $PROMETHEUS_POD"
}

# Check if we can access OpenShift
if ! command -v oc &>/dev/null; then
  fail "oc command not found. Please install OpenShift CLI."
fi

if ! oc whoami &>/dev/null 2>&1; then
  fail "Not logged into OpenShift. Run 'oc login' first."
fi

find_prometheus_pod

SEQ=5000
NOW=$(date +%s)
DAY=86400
HOUR=3600
WEEK=$((7 * DAY))

sha256() { printf "sha256:%064x" "$1"; }
commit_hash() { printf "%040x" "$1"; }

# Initialize metrics file with OpenMetrics headers
cat > "$METRICS_FILE" <<EOF
# TYPE commit_timestamp gauge
# HELP commit_timestamp Timestamp when code was committed
# TYPE deploy_timestamp gauge
# HELP deploy_timestamp Timestamp when code was deployed
# TYPE failure_creation_timestamp gauge
# HELP failure_creation_timestamp Timestamp when failure/incident was created
# TYPE failure_resolution_timestamp gauge
# HELP failure_resolution_timestamp Timestamp when failure/incident was resolved
EOF

# emit_metric type labels value timestamp_seconds
emit_metric() {
  local type="$1" labels="$2" value="$3" ts_sec="$4"
  local ts_ms=$((ts_sec * 1000))
  echo "${type}{${labels}} ${value} ${ts_ms}" >> "$METRICS_FILE"
}

# send_deploy app namespace commit_ts lead_time_seconds
send_deploy() {
  local app="$1" ns="$2" commit_ts="$3" lead_time="$4"
  SEQ=$((SEQ + 1))
  local img=$(sha256 $SEQ)
  local hash=$(commit_hash $SEQ)
  local deploy_ts=$((commit_ts + lead_time))
  [[ $deploy_ts -gt $NOW ]] && deploy_ts=$NOW

  # Commit timestamp metric
  emit_metric "commit_timestamp" \
    "app=\"/${app}/\",commit=\"${hash}\",image_sha=\"${img}\",exported_namespace=\"${ns}\"" \
    "$commit_ts" "$commit_ts"

  # Deploy timestamp metric
  emit_metric "deploy_timestamp" \
    "app=\"/${app}/\",image_sha=\"${img}\",exported_namespace=\"${ns}\"" \
    "$deploy_ts" "$deploy_ts"
}

# send_incident app failure_id created_ts ttrs_seconds
send_incident() {
  local app="$1" fail_id="$2" created_ts="$3" ttrs="$4"

  # Failure creation metric
  emit_metric "failure_creation_timestamp" \
    "app=\"/${app}/\",issue_number=\"${fail_id}\"" \
    "$created_ts" "$created_ts"

  if [[ "$ttrs" != "open" ]]; then
    local resolved_ts=$((created_ts + ttrs))
    [[ $resolved_ts -gt $NOW ]] && resolved_ts=$((NOW - 60))

    # Failure resolution metric
    emit_metric "failure_resolution_timestamp" \
      "app=\"/${app}/\",issue_number=\"${fail_id}\"" \
      "$resolved_ts" "$resolved_ts"
  fi
}

echo ""
echo "================================================================"
echo "  Seeding 6 months of DORA metrics for 4 engineering teams"
echo "================================================================"

# ======================================================================
# FRONTEND TEAM - Elite performers
# Story: Mature CI/CD, trunk-based dev, feature flags. Started good,
#        got even better. Ships multiple times per day.
# ======================================================================
echo ""
echo "[frontend] Elite performer - trunk-based development"
echo "  History: 6 months, ~180 deploys, 8 incidents"

app="frontend"
ns="frontend-prod"
fail_seq=0

for month in $(seq 5 -1 0); do
  # Start of each month's window: month 0 = last 30 days, month 5 = 150-180 days ago
  base=$((NOW - (month + 1) * 30 * DAY))
  # Improving lead time: 90s -> 25s over 6 months
  lt_base=$((90 - month * 10 - (5 - month) * 3))
  [[ $lt_base -lt 20 ]] && lt_base=20
  # High deploy frequency: 25-35 per month
  deploys=$((28 + RANDOM % 8))

  for d in $(seq 1 $deploys); do
    jitter=$((RANDOM % (30 * DAY)))
    ts=$((base + jitter))
    lt=$((lt_base + RANDOM % 15))
    send_deploy "$app" "$ns" "$ts" "$lt"
  done

  # Rare incidents: ~1-2 per month, fast recovery (2-10 min)
  if (( RANDOM % 3 != 0 )); then
    fail_seq=$((fail_seq + 1))
    inc_ts=$((base + RANDOM % (30 * DAY)))
    ttrs=$(( 120 + RANDOM % 480 ))
    send_incident "$app" "FRONT-${fail_seq}" "$inc_ts" "$ttrs"
    echo "  month -${month}: ~${deploys} deploys, lt=${lt_base}s, incident FRONT-${fail_seq} (${ttrs}s MTTR)"
  else
    echo "  month -${month}: ~${deploys} deploys, lt=${lt_base}s, no incidents"
  fi
done

# ======================================================================
# API-GATEWAY TEAM - Medium performers, steady improvement
# Story: Migrated from monolith 6 months ago. Initially slow with
#        manual QA gates. Introduced automated testing in month 3,
#        lead times dropped significantly.
# ======================================================================
echo ""
echo "[api-gateway] Medium performer - improving after monolith migration"
echo "  History: 6 months, ~90 deploys, 15 incidents"

app="api-gateway"
ns="api-prod"
fail_seq=0

for month in $(seq 5 -1 0); do
  # Start of each month's window: month 0 = last 30 days, month 5 = 150-180 days ago
  base=$((NOW - (month + 1) * 30 * DAY))
  # Lead time improving: 15min -> 3min over 6 months (big drop at month 3)
  if (( month > 3 )); then
    lt_base=$((900 - (5 - month) * 60))   # 15min -> 12min
  elif (( month > 1 )); then
    lt_base=$((480 - (3 - month) * 120))  # 8min -> 4min (automation kicked in)
  else
    lt_base=$((240 - (1 - month) * 40))   # 4min -> 3min
  fi
  # Deploy frequency increasing: 8 -> 20 per month
  deploys=$((8 + (5 - month) * 2 + RANDOM % 4))

  for d in $(seq 1 $deploys); do
    jitter=$((RANDOM % (30 * DAY)))
    ts=$((base + jitter))
    lt=$((lt_base + RANDOM % (lt_base / 3 + 1)))
    send_deploy "$app" "$ns" "$ts" "$lt"
  done

  # Moderate incidents: 2-3 per month early, 1-2 later. MTTR improving.
  incidents=$((3 - (5 - month) / 2))
  [[ $incidents -lt 1 ]] && incidents=1
  for i in $(seq 1 $incidents); do
    fail_seq=$((fail_seq + 1))
    inc_ts=$((base + RANDOM % (30 * DAY)))
    ttrs=$((300 + RANDOM % 600 + month * 120))
    send_incident "$app" "API-${fail_seq}" "$inc_ts" "$ttrs"
  done
  echo "  month -${month}: ~${deploys} deploys, lt=$((lt_base/60))m$((lt_base%60))s, ${incidents} incidents"
done

# ======================================================================
# PAYMENT-SERVICE TEAM - Low performers, getting worse
# Story: Legacy codebase, high coupling, no automated tests.
#        Lead times increasing as tech debt accumulates. Frequent
#        production incidents with long recovery. One open incident.
# ======================================================================
echo ""
echo "[payment-service] Low performer - struggling with tech debt"
echo "  History: 6 months, ~40 deploys, 25 incidents (1 open)"

app="payment-service"
ns="payments-prod"
fail_seq=0

for month in $(seq 5 -1 0); do
  # Start of each month's window: month 0 = last 30 days, month 5 = 150-180 days ago
  base=$((NOW - (month + 1) * 30 * DAY))
  # Lead time getting WORSE: 10min -> 25min (more manual steps, longer QA)
  lt_base=$((600 + (5 - month) * 180))
  # Low deploy frequency, getting lower: 8 -> 5 per month
  deploys=$((8 - (5 - month) / 2 + RANDOM % 3))
  [[ $deploys -lt 3 ]] && deploys=3

  for d in $(seq 1 $deploys); do
    jitter=$((RANDOM % (30 * DAY)))
    ts=$((base + jitter))
    lt=$((lt_base + RANDOM % (lt_base / 4 + 1)))
    send_deploy "$app" "$ns" "$ts" "$lt"
  done

  # Frequent incidents: 3-5 per month, MTTR getting worse
  incidents=$((3 + (5 - month) / 2 + RANDOM % 2))
  for i in $(seq 1 $incidents); do
    fail_seq=$((fail_seq + 1))
    inc_ts=$((base + RANDOM % (30 * DAY)))
    # Last incident is open (unresolved)
    if (( month == 0 && i == incidents )); then
      send_incident "$app" "PAY-${fail_seq}" "$inc_ts" "open"
      echo "  month -${month}: ~${deploys} deploys, lt=$((lt_base/60))m, ${incidents} incidents (1 OPEN)"
    else
      ttrs=$((600 + RANDOM % 1200 + (5 - month) * 300))
      send_incident "$app" "PAY-${fail_seq}" "$inc_ts" "$ttrs"
    fi
  done
  (( month != 0 )) && echo "  month -${month}: ~${deploys} deploys, lt=$((lt_base/60))m, ${incidents} incidents"
done

# ======================================================================
# INVENTORY-SERVICE TEAM - Turnaround story
# Story: Was the worst team 6 months ago. New tech lead joined,
#        introduced TDD, CI/CD pipeline, pair programming. Dramatic
#        improvement over last 3 months. Now approaching medium level.
# ======================================================================
echo ""
echo "[inventory-service] Turnaround - dramatic improvement in last 3 months"
echo "  History: 6 months, ~70 deploys, 18 incidents"

app="inventory-service"
ns="inventory-prod"
fail_seq=0

for month in $(seq 5 -1 0); do
  # Start of each month's window: month 0 = last 30 days, month 5 = 150-180 days ago
  base=$((NOW - (month + 1) * 30 * DAY))
  # Lead time: started terrible (20min), stayed bad for 3 months,
  # then rapid improvement: 20min -> 18min -> 16min -> 8min -> 4min -> 2min
  if (( month > 3 )); then
    lt_base=$((1200 - (5 - month) * 120))  # 20min -> 16min (slow progress)
  elif (( month > 1 )); then
    lt_base=$((960 - (3 - month) * 300))   # 16min -> 6min (TDD + CI/CD kick in)
  else
    lt_base=$((360 - (1 - month) * 180))   # 6min -> 3min (team is flying)
  fi
  [[ $lt_base -lt 120 ]] && lt_base=120
  # Deploy freq: started at 5/month, now 20/month
  if (( month > 3 )); then
    deploys=$((5 + RANDOM % 3))
  elif (( month > 1 )); then
    deploys=$((10 + (3 - month) * 3 + RANDOM % 3))
  else
    deploys=$((18 + (1 - month) * 4 + RANDOM % 4))
  fi

  for d in $(seq 1 $deploys); do
    jitter=$((RANDOM % (30 * DAY)))
    ts=$((base + jitter))
    lt=$((lt_base + RANDOM % (lt_base / 4 + 1)))
    send_deploy "$app" "$ns" "$ts" "$lt"
  done

  # Incidents: 4-5/month early (chaos), dropping to 1/month now
  if (( month > 3 )); then
    incidents=$((4 + RANDOM % 2))
  elif (( month > 1 )); then
    incidents=$((2 + RANDOM % 2))
  else
    incidents=$((1))
  fi
  for i in $(seq 1 $incidents); do
    fail_seq=$((fail_seq + 1))
    inc_ts=$((base + RANDOM % (30 * DAY)))
    # MTTR also improving
    if (( month > 3 )); then
      ttrs=$((900 + RANDOM % 1800))
    elif (( month > 1 )); then
      ttrs=$((300 + RANDOM % 600))
    else
      ttrs=$((120 + RANDOM % 300))
    fi
    send_incident "$app" "INV-${fail_seq}" "$inc_ts" "$ttrs"
  done
  echo "  month -${month}: ~${deploys} deploys, lt=$((lt_base/60))m$((lt_base%60))s, ${incidents} incidents"
done

# Add EOF marker for OpenMetrics format
echo "# EOF" >> "$METRICS_FILE"

echo ""
echo "================================================================"
echo "  Metrics file generated: $METRICS_FILE"
echo "================================================================"

# Count metrics
commit_count=$(grep -c "^commit_timestamp{" "$METRICS_FILE" || true)
deploy_count=$(grep -c "^deploy_timestamp{" "$METRICS_FILE" || true)
failure_created=$(grep -c "^failure_creation_timestamp{" "$METRICS_FILE" || true)
failure_resolved=$(grep -c "^failure_resolution_timestamp{" "$METRICS_FILE" || true)

echo ""
echo "  Commit metrics:    $commit_count"
echo "  Deploy metrics:    $deploy_count"
echo "  Failures created:  $failure_created"
echo "  Failures resolved: $failure_resolved"
echo "  Total metrics:     $((commit_count + deploy_count + failure_created + failure_resolved))"
echo "  File size:         $(du -h "$METRICS_FILE" | cut -f1)"
echo ""

# ======================================================================
# Import metrics into Prometheus using backfill
# ======================================================================
echo "================================================================"
echo "  Importing metrics into Prometheus (backfill)"
echo "================================================================"
echo ""

log "Copying metrics file to Prometheus pod..."
oc cp "$METRICS_FILE" "${NAMESPACE}/${PROMETHEUS_POD}:/prometheus/pelorus-seed-metrics.txt" -c prometheus

log "Creating TSDB blocks from metrics..."
oc exec -n "$NAMESPACE" "$PROMETHEUS_POD" -c prometheus -- \
  sh -c 'TMPDIR=/prometheus promtool tsdb create-blocks-from openmetrics \
    /prometheus/pelorus-seed-metrics.txt \
    /prometheus'

log "Cleaning up temporary file in pod..."
oc exec -n "$NAMESPACE" "$PROMETHEUS_POD" -c prometheus -- \
  rm -f /prometheus/pelorus-seed-metrics.txt

log "Cleaning up local metrics file..."
rm -f "$METRICS_FILE"

echo ""
echo "================================================================"
echo "  Done - seeded ~380 deploys and ~66 incidents over 6 months"
echo "================================================================"
echo ""
echo "Team performance summary:"
echo ""
echo "  frontend          Elite     25s lead time, 30 deploys/month, <10% failure rate"
echo "                              Mature CI/CD, trunk-based dev, feature flags"
echo ""
echo "  api-gateway       Medium    3min lead time (was 15min), improving steadily"
echo "                              Monolith migration, automated testing since month 3"
echo ""
echo "  payment-service   Low       25min lead time (getting worse), high failure rate"
echo "                              Legacy code, manual QA, tech debt accumulating"
echo ""
echo "  inventory-service Turnaround 3min lead time (was 20min), dramatic improvement"
echo "                              New tech lead, TDD, CI/CD introduced 3 months ago"
echo ""
echo "The metrics have been imported directly into Prometheus's TSDB."
echo "Set Grafana time range to 'Last 6 months' or 'Last 90 days' for full history."
echo "Prometheus may need ~30s to reload and evaluate recording rules."
echo ""
