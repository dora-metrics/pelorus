#!/usr/bin/env bash
#
# Seed Pelorus with realistic DORA metrics via the webhook exporter.
# Creates 6 months of project history for 4 teams with different
# performance profiles, improvement arcs, and incident patterns.
#
# The webhook exporter must be running with PELORUS_TIMESTAMP_THRESHOLD_MINUTES
# set high enough (e.g. 525600 for 1 year). The install script handles this
# automatically when seeding.
#
# Usage:
#   ./demo/seed-metrics.sh                          # auto-detect endpoint
#   ./demo/seed-metrics.sh http://localhost:8080     # explicit endpoint
#   WEBHOOK_URL=http://localhost:8080 ./demo/seed-metrics.sh
#
set -euo pipefail

WEBHOOK_URL="${1:-${WEBHOOK_URL:-}}"

if [[ -z "$WEBHOOK_URL" ]]; then
  if command -v oc &>/dev/null && oc whoami &>/dev/null 2>&1; then
    echo "Starting port-forward to webhook-exporter..."
    oc port-forward -n pelorus svc/webhook-exporter 18080:8080 &>/dev/null &
    PF_PID=$!
    trap "kill $PF_PID 2>/dev/null || true" EXIT
    sleep 2
    WEBHOOK_URL="http://localhost:18080"
  else
    echo "Usage: $0 <webhook-url>"
    echo "  e.g. $0 http://localhost:8080"
    exit 1
  fi
fi

echo "Using webhook endpoint: $WEBHOOK_URL"

SEQ=5000
NOW=$(date +%s)
DAY=86400
HOUR=3600
WEEK=$((7 * DAY))

sha256() { printf "sha256:%064x" "$1"; }
commit_hash() { printf "%040x" "$1"; }

send() {
  local event="$1"; shift
  curl -sf -o /dev/null -X POST "$WEBHOOK_URL/pelorus/webhook" \
    -H "Content-Type: application/json" \
    -H "User-Agent: Pelorus-Webhook/demo-seed" \
    -H "X-Pelorus-Event: $event" \
    -d "$1" || echo "    WARN: failed to send $event"
}

# send_deploy app namespace commit_ts lead_time_seconds
send_deploy() {
  local app="$1" ns="$2" commit_ts="$3" lead_time="$4"
  SEQ=$((SEQ + 1))
  local img=$(sha256 $SEQ)
  local hash=$(commit_hash $SEQ)
  local deploy_ts=$((commit_ts + lead_time))
  [[ $deploy_ts -gt $NOW ]] && deploy_ts=$NOW

  send committime "{\"app\":\"$app\",\"commit_hash\":\"$hash\",\"image_sha\":\"$img\",\"namespace\":\"$ns\",\"timestamp\":$commit_ts}"
  send deploytime "{\"app\":\"$app\",\"image_sha\":\"$img\",\"namespace\":\"$ns\",\"timestamp\":$deploy_ts}"
}

# send_incident app failure_id created_ts ttrs_seconds
send_incident() {
  local app="$1" fail_id="$2" created_ts="$3" ttrs="$4"
  send failure "{\"app\":\"$app\",\"failure_id\":\"$fail_id\",\"failure_event\":\"created\",\"timestamp\":$created_ts}"
  if [[ "$ttrs" != "open" ]]; then
    local resolved_ts=$((created_ts + ttrs))
    [[ $resolved_ts -gt $NOW ]] && resolved_ts=$((NOW - 60))
    send failure "{\"app\":\"$app\",\"failure_id\":\"$fail_id\",\"failure_event\":\"resolved\",\"timestamp\":$resolved_ts}"
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
  base=$((NOW - month * 30 * DAY))
  # Improving lead time: 90s -> 25s over 6 months
  lt_base=$((90 - month * 10 - (5 - month) * 3))
  [[ $lt_base -lt 20 ]] && lt_base=20
  # High deploy frequency: 25-35 per month
  deploys=$((28 + RANDOM % 8))

  for d in $(seq 1 $deploys); do
    jitter=$((RANDOM % (25 * DAY)))
    ts=$((base + jitter))
    [[ $ts -gt $NOW ]] && continue
    lt=$((lt_base + RANDOM % 15))
    send_deploy "$app" "$ns" "$ts" "$lt"
  done

  # Rare incidents: ~1-2 per month, fast recovery (2-10 min)
  if (( RANDOM % 3 != 0 )); then
    fail_seq=$((fail_seq + 1))
    inc_ts=$((base + RANDOM % (20 * DAY)))
    [[ $inc_ts -gt $NOW ]] && continue
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
  base=$((NOW - month * 30 * DAY))
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
    jitter=$((RANDOM % (25 * DAY)))
    ts=$((base + jitter))
    [[ $ts -gt $NOW ]] && continue
    lt=$((lt_base + RANDOM % (lt_base / 3 + 1)))
    send_deploy "$app" "$ns" "$ts" "$lt"
  done

  # Moderate incidents: 2-3 per month early, 1-2 later. MTTR improving.
  incidents=$((3 - (5 - month) / 2))
  [[ $incidents -lt 1 ]] && incidents=1
  for i in $(seq 1 $incidents); do
    fail_seq=$((fail_seq + 1))
    inc_ts=$((base + RANDOM % (20 * DAY)))
    [[ $inc_ts -gt $NOW ]] && continue
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
  base=$((NOW - month * 30 * DAY))
  # Lead time getting WORSE: 10min -> 25min (more manual steps, longer QA)
  lt_base=$((600 + (5 - month) * 180))
  # Low deploy frequency, getting lower: 8 -> 5 per month
  deploys=$((8 - (5 - month) / 2 + RANDOM % 3))
  [[ $deploys -lt 3 ]] && deploys=3

  for d in $(seq 1 $deploys); do
    jitter=$((RANDOM % (25 * DAY)))
    ts=$((base + jitter))
    [[ $ts -gt $NOW ]] && continue
    lt=$((lt_base + RANDOM % (lt_base / 4 + 1)))
    send_deploy "$app" "$ns" "$ts" "$lt"
  done

  # Frequent incidents: 3-5 per month, MTTR getting worse
  incidents=$((3 + (5 - month) / 2 + RANDOM % 2))
  for i in $(seq 1 $incidents); do
    fail_seq=$((fail_seq + 1))
    inc_ts=$((base + RANDOM % (20 * DAY)))
    [[ $inc_ts -gt $NOW ]] && continue
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
  base=$((NOW - month * 30 * DAY))
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
    jitter=$((RANDOM % (25 * DAY)))
    ts=$((base + jitter))
    [[ $ts -gt $NOW ]] && continue
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
    inc_ts=$((base + RANDOM % (20 * DAY)))
    [[ $inc_ts -gt $NOW ]] && continue
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
echo "Set Grafana time range to 'Last 6 months' or 'Last 90 days' for full history."
echo "Prometheus needs ~60s to scrape and evaluate recording rules."
