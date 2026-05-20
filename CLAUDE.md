# Pelorus Project Context

## Project Overview

Pelorus is a DORA (DevOps Research and Assessment) metrics platform for OpenShift/Kubernetes that tracks:
- **Deployment Frequency**: How often code is deployed
- **Lead Time for Change**: Time from commit to deployment
- **Time to Restore Service**: Time to recover from failures
- **Change Failure Rate**: Percentage of deployments causing incidents

The system consists of:
- **Exporters**: Collect metrics (committime, deploytime, failure, webhook)
- **Prometheus**: Stores time-series metrics data
- **Grafana**: Visualizes DORA metrics dashboards
- **Pelorus Operator**: Helm-based operator managing the deployment

## Recent Work: Demo Seed Metrics Issue

### Problem Statement

The demo seed script (`./demo/seed-metrics.sh`) was designed to generate 6 months of historical DORA metrics for 4 fictional teams, but all metrics appeared timestamped as "NOW" in Grafana instead of being distributed over the past 6 months.

### Root Causes Identified

1. **Prometheus Pod Restart Loop** (FIXED)
   - **Cause**: Helm template used `randAlphaNum 32` for OAuth cookie secret
   - **Effect**: Generated new random value on every reconciliation, triggering Prometheus pod deletion
   - **Fix**: Modified templates to generate cookie secret once and persist in Kubernetes Secret
   - **Files**: `pelorus-operator/helm-charts/pelorus/templates/prometheus-oauth-cookie-secret.yaml`

2. **Webhook Exporter Timestamp Handling** (FIXED)
   - **Cause**: Explicit timestamps weren't being passed to Prometheus metrics format
   - **Effect**: Webhook had correct timestamp values but Prometheus used scrape time
   - **Fix**: Modified `in_memory_metric.py` to pass timestamp as explicit sample timestamp
   - **Files**: `exporters/webhook/store/in_memory_metric.py`

3. **ServiceMonitor honorTimestamps** (FIXED)
   - **Cause**: ServiceMonitor configured with `honorTimestamps: false`
   - **Effect**: Prometheus ignored explicit timestamps from webhook exporter
   - **Fix**: Changed to `honorTimestamps: true`
   - **Files**: `pelorus-operator/helm-charts/pelorus/charts/exporters/templates/servicemonitor.yaml`

4. **Scrape-Based Approach Limitations** (ARCHITECTURAL CHANGE)
   - **Cause**: Prometheus scrape model rejects samples "too old or too far into the future"
   - **Effect**: Historical metrics dropped during ingestion
   - **Solution**: Switched from webhook POSTing to **Prometheus backfill**

### Solution: Prometheus Backfill

Refactored `./demo/seed-metrics.sh` to use Prometheus's offline backfill feature:
- Generates OpenMetrics format file with historical timestamps
- Uses `promtool tsdb create-blocks-from openmetrics` to create TSDB blocks
- Imports blocks directly into Prometheus data directory
- **Requires persistent storage** to survive pod restarts

### Changes Made

#### 1. Install Script (`demo/install.sh`)
- Added `OAUTH_COOKIE_SECRET` variable generation
- Enabled persistent storage: `prometheus_storage: true`
- Set PVC capacity: `prometheus_storage_pvc_capacity: 5Gi`
- Added cookie secret to Pelorus CR spec

#### 2. Operator Templates
- Created `prometheus-oauth-cookie-secret.yaml` template
- Modified `prometheus-cr.yaml` to reference cookie secret from Secret
- Updated `servicemonitor.yaml` to enable `honorTimestamps: true`
- Updated CRD to include `prometheus_oauth_cookie_secret` field

#### 3. Webhook Exporter (`exporters/webhook/store/in_memory_metric.py`)
```python
# Modified add_metric to pass timestamp as both value AND explicit sample timestamp
if len(args) >= 2 and isinstance(args[1], (int, float)) and 'timestamp' not in kwargs:
    kwargs['timestamp'] = int(args[1])
```

#### 4. Seed Metrics Script (`demo/seed-metrics.sh`)
Complete refactor:
- Generates OpenMetrics file instead of POSTing to webhook
- Uses `promtool tsdb create-blocks-from openmetrics`
- Imports blocks directly into `/prometheus` directory
- Requires Prometheus persistent storage to be enabled

### Current Status (Updated May 18, 2026)

✅ **SOLUTION IDENTIFIED: Enable Out-of-Order Ingestion**

**Root Cause**: Out-of-order ingestion was completely disabled (`outofordertimewindow: 0`), which caused Prometheus to reject/ignore backfilled historical data during queries.

**Working Components:**
- ✅ Prometheus pod restart loop fixed (OAuth cookie secret persisted)
- ✅ Webhook exporter provides explicit timestamps via `in_memory_metric.py`
- ✅ ServiceMonitor configured with `honorTimestamps: true`
- ✅ Persistent storage enabled and working (PVC retains data across restarts)
- ✅ Backfill script successfully generates 540 metrics spanning 150 days
- ✅ TSDB blocks created correctly with proper timestamps (Nov 2025 → Apr 2026)
- ✅ Helm templates configured correctly for OOO support
- ✅ Install script sets `prometheus_out_of_order_time_window: 180d`

**Issue Identified:**
- ❌ Prometheus Operator v0.56.3 (2022) doesn't support `additionalArgs` for Prometheus CRD
- ✅ Feature added in v0.59.0 (September 2022), available in beta channel (v0.70.0+)
- ✅ Updated install script to verify operator version and warn if too old

**What Was Learned:**
- Auto-compaction wasn't the problem—OOO being disabled was
- Remote Write API wouldn't solve the issue (same OOO limitation)
- Backfill is the correct approach for bulk historical data
- Prometheus 3.11.3 supports OOO via `--storage.tsdb.out-of-order-time-window=180d` flag

**SCC Issue Resolution (May 20, 2026):** ✅ **RESOLVED**

**Problem:**
- Prometheus Operator v0.70.0 from operatorhubio-catalog failed to deploy in OpenShift
- **Root Cause**: CSV hardcoded `runAsUser: 65534` which conflicts with OpenShift SCC namespace UID ranges
- **Error**: `unable to validate against any security context constraint: provider restricted-v2: .containers[0].runAsUser: Invalid value: 65534: must be in the ranges: [1000730000, 1000739999]`
- **Why it happened**: operatorhubio-catalog is designed for vanilla Kubernetes (no SCCs)

**Solution: CSV Patch**

Patched the installed CSV to remove the hardcoded `runAsUser`, allowing OpenShift to assign a UID from the namespace range:

```bash
# Patch the CSV to remove hardcoded runAsUser
oc patch csv prometheusoperator.v0.70.0 -n pelorus --type=json \
  -p='[{"op": "remove", "path": "/spec/install/spec/deployments/0/spec/template/spec/securityContext/runAsUser"}]'

# Delete deployment to trigger recreation with patched spec
oc delete deployment prometheus-operator -n pelorus

# OLM recreates deployment with OpenShift-assigned UID (e.g., 1000730000)
```

**Result:**
- ✅ Operator pod runs as UID within OpenShift namespace range
- ✅ No elevated privileges required (no anyuid SCC)
- ✅ Maintains `runAsNonRoot: true` security posture
- ✅ Full `additionalArgs` support for OOO ingestion

**Important Notes:**
- **Patch may need reapplication** if operator is upgraded via OLM
- **Not needed for fresh installs** if using the current `demo/install.sh` (applies patch automatically)
- **Pelorus requires a dedicated Prometheus** - OpenShift User Workload Monitoring is not suitable as Pelorus must remain decoupled from platform services

**Analysis Documents:**
- `demo/ADD_OPERATORHUBIO_CATALOG.md` - Technical details of k8s-operatorhub catalog
- `demo/cleanup-prometheus.sh` - Automated cleanup script for operator migration

### Lessons Learned

1. **Backfill Works for Block Creation**: `promtool tsdb create-blocks-from openmetrics` successfully creates blocks with historical timestamps
2. **Persistent Storage is Required**: Without PVC, backfilled blocks are lost on pod restart
3. **Prometheus Loads Blocks on Startup**: Confirmed via "Found healthy block" logs showing Nov 2025 timestamps
4. **OOO Configuration is Critical**: Without out-of-order ingestion enabled, Prometheus won't properly query historical backfilled data
5. **Operator Version Matters**: Prometheus Operator v0.56.3 doesn't support `additionalArgs` (added in v0.59.0)
6. **Remote Write Not a Silver Bullet**: Remote Write API faces the same OOO limitation as backfill
7. **Auto-Compaction is Not the Problem**: Initial theory was wrong—compaction works correctly when OOO is enabled

### Solution: Enable Out-of-Order (OOO) Ingestion ✅

**Updated: May 18, 2026**

The root cause of historical backfill data being un-queryable was **out-of-order ingestion being completely disabled** (`outofordertimewindow: 0`). Remote Write API is NOT the solution—it faces the same OOO limitation.

#### Investigation Results

1. **Helm Templates Already Correct** ✅
   - `prometheus-cr.yaml` properly configured with `additionalArgs` support
   - `values.yaml` has `prometheus_out_of_order_time_window` setting (commented out)
   - `install.sh` sets `prometheus_out_of_order_time_window: 180d`

2. **Prometheus Operator Version Issue** ❌
   - Old installations used **Prometheus Operator v0.56.3** (from 2022)
   - `additionalArgs` field support for Prometheus CRD was added in **v0.59.0** (September 2, 2022)
   - OpenShift community-operators catalog is severely outdated (4 years behind)
   - **WORKAROUND**: Using k8s-operatorhub catalog provides v0.70.0 with full OOO support

3. **Temporary Catalog Source (Development Only)** ⚠️
   - **Status**: `demo/install.sh` now installs `operatorhubio-catalog` from k8s-operatorhub
   - **Why**: OpenShift's community-operators only has v0.56.3; k8s-operatorhub has v0.70.0
   - **Temporary**: This is a development/demo workaround, NOT for production deployments
   - **TODO**: Remove this workaround once OpenShift community-operators is updated
   - **TODO**: Create PR to openshift/community-operators to sync with k8s-operatorhub versions
   - See `demo/ADD_OPERATORHUBIO_CATALOG.md` for technical details

4. **Remote Write Investigation** 🔍
   - Prometheus Remote Write spec allows historical timestamps
   - However, receivers reject old samples when OOO is disabled
   - Switching to Remote Write does NOT solve the OOO problem
   - Backfill is actually the CORRECT tool for bulk historical ingestion

#### Changes Made (May 18, 2026)

1. **install.sh** - Added operator version verification:
   ```bash
   # Checks installed Prometheus Operator version
   # Warns if < v0.59.0 (won't support OOO)
   # Confirms if >= v0.59.0 (supports OOO)
   ```

2. **Configuration Already in Place**:
   - Helm template: `additionalArgs` with `storage.tsdb.out-of-order-time-window`
   - Install script: Sets `180d` OOO window for 6-month demo data
   - Operator subscription: Uses `beta` channel (provides v0.70.0+)

#### Deployment Steps

**Option 1: Fresh Install**
```bash
cd /projects/pelorus
./demo/install.sh
# Will install Prometheus Operator v0.70.0+ with OOO enabled
```

**Option 2: Upgrade Existing Installation**
```bash
# Delete old operator subscription
oc delete subscription prometheus -n pelorus
oc delete csv -n pelorus -l operators.coreos.com/prometheus.pelorus

# Re-run install (installs latest from beta channel)
./demo/install.sh
```

#### Verification Commands

**Check Operator Version:**
```bash
oc get csv -n pelorus | grep prometheus
# Should show v0.59.0 or higher
```

**Verify OOO Configuration Applied:**
```bash
oc get prometheus prometheus-pelorus -n pelorus -o yaml | grep -A 3 additionalArgs
# Should output:
# additionalArgs:
# - name: storage.tsdb.out-of-order-time-window
#   value: "180d"
```

**Confirm Prometheus Container Args:**
```bash
oc get pod prometheus-prometheus-pelorus-0 -n pelorus \
  -o jsonpath='{.spec.containers[?(@.name=="prometheus")].args}' | grep out-of-order
# Should output: --storage.tsdb.out-of-order-time-window=180d
```

**Query Prometheus Config:**
```bash
oc port-forward -n pelorus svc/prometheus-pelorus 9090:9091
curl http://localhost:9090/api/v1/status/config | jq '.data.yaml' | grep outofordertimewindow
# Should output: outofordertimewindow: 180d (not 0)
```

#### Testing Historical Data

Once OOO is enabled, backfill should work:
```bash
./demo/seed-metrics.sh
# Creates 6 months of historical data (Nov 2025 → Apr 2026)

# In Grafana: Set time range to "Last 6 months"
# Historical metrics should now be visible
```

### Why This Solution Works

| Issue | Root Cause | Solution |
|-------|------------|----------|
| Backfill blocks created but not queryable | OOO disabled (`outofordertimewindow: 0`) | Enable OOO with `180d` window |
| Operator doesn't apply `additionalArgs` | Prometheus Operator v0.56.3 too old | Use v0.59.0+ from beta channel |
| Auto-compaction deletes old blocks | Only happens when OOO disabled | Enabling OOO fixes compaction behavior |

### Rejected Alternatives

1. **Disable Auto-Compaction**: Too risky, affects normal operations
2. **Remote Write API**: Faces same OOO limitation, more complex to implement
3. **Accept 1-2 Day Limitation**: Defeats purpose of 6-month demo data
4. **External Backfill Tool**: Unnecessary complexity once OOO is enabled

### TODO: Upstream Improvements

1. **Update OpenShift community-operators catalog** 🎯 HIGH PRIORITY
   - **Problem**: OpenShift's `community-operators` catalog has Prometheus Operator v0.56.3 (May 2022)
   - **Issue**: v0.56.3 doesn't support `additionalArgs` (added in v0.59.0)
   - **Current Workaround**: `demo/install.sh` uses k8s-operatorhub's `operatorhubio-catalog` which has v0.70.0
   - **Long-term Fix**: Create PR to openshift/community-operators to sync with k8s-operatorhub versions
   - **Target**: Get at least v0.59.0, ideally v0.70.0+ into OpenShift catalog with OpenShift SCC compatibility
   - **Impact**: Once fixed, remove temporary catalog source AND CSV patch from demo/install.sh
   - **References**:
     - k8s-operatorhub has v0.70.0: https://github.com/k8s-operatorhub/community-operators
     - OpenShift catalog: https://github.com/redhat-openshift-ecosystem/community-operators-prod
     - Upstream releases: https://github.com/prometheus-operator/prometheus-operator/releases

2. **Automate CSV Patch in install.sh** 🔧 MEDIUM PRIORITY
   - **Current State**: CSV patch must be applied manually after operator installation
   - **Goal**: Detect if CSV has `runAsUser: 65534` and apply patch automatically
   - **Benefit**: Ensures fresh installs work without manual intervention
   - **Note**: May still be needed after operator upgrades via OLM

3. **Document OOO Requirements in Pelorus Docs**
   - Add section to main README about Prometheus Operator version requirements
   - Document that historical backfill requires v0.59.0+ for `additionalArgs` support
   - Include troubleshooting steps for version verification
   - Document CSV patch workaround for OpenShift SCC issues

## Architecture Notes

### Persistent Storage Requirement

The backfill approach **requires** persistent storage because:
- TSDB blocks are created in `/prometheus` directory
- Without PVC, blocks are lost on pod restart (emptyDir)
- For development/demo: Use `crc-csi-hostpath-provisioner` (CRC)
- For production: Use cloud provider storage class

### Storage Classes by Environment

```yaml
# CRC (local development)
prometheus_storage_pvc_storageclass: "crc-csi-hostpath-provisioner"

# AWS
prometheus_storage_pvc_storageclass: "gp2"  # or "gp3"

# Azure
prometheus_storage_pvc_storageclass: "managed-premium"
```

### Demo Data Profile

The seed script generates realistic data for 4 teams:

1. **frontend** - Elite performer
   - 30 deploys/month, 25s lead time
   - Trunk-based dev, feature flags
   - ~180 deploys, 8 incidents over 6 months

2. **api-gateway** - Medium performer, improving
   - Improving from 15min to 3min lead time
   - Monolith migration, automation introduced month 3
   - ~90 deploys, 15 incidents over 6 months

3. **payment-service** - Low performer, declining
   - Getting worse: 10min → 25min lead time
   - Legacy code, tech debt accumulating
   - ~40 deploys, 25 incidents over 6 months (1 still open)

4. **inventory-service** - Turnaround story
   - Dramatic improvement: 20min → 3min lead time
   - New tech lead, TDD/CI/CD introduced
   - ~70 deploys, 18 incidents over 6 months

Total: ~380 deploys, ~66 incidents spanning 6 months

## Key Files Reference

### Operator & Helm Charts
- `pelorus-operator/helm-charts/pelorus/values.yaml` - Default values
- `pelorus-operator/helm-charts/pelorus/templates/prometheus-cr.yaml` - Prometheus CR
- `pelorus-operator/helm-charts/pelorus/templates/prometheus-oauth-cookie-secret.yaml` - Cookie secret
- `pelorus-operator/helm-charts/pelorus/charts/exporters/templates/servicemonitor.yaml` - Scrape config
- `pelorus-operator/config/crd/bases/charts.pelorus.dora-metrics.io_peloruses.yaml` - CRD schema

### Exporters
- `exporters/webhook/app.py` - Webhook exporter main
- `exporters/webhook/store/in_memory_metric.py` - Metric storage (timestamp fix here)
- `exporters/webhook/models/pelorus_webhook.py` - Pydantic models

### Demo Scripts
- `demo/install.sh` - Main installation script
- `demo/seed-metrics.sh` - Generate and import historical data
- `demo/clear-metrics.sh` - Clear metrics from Prometheus
- `demo/REMOTE_WRITE_EXPERIMENT_FINDINGS.md` - Detailed investigation notes (May 15-18, 2026)

## Development Environment

The current setup uses CodeReady Containers (CRC) - OpenShift local development:
- Namespace: `pelorus`
- Operator namespace: `pelorus-operator-system`
- Storage class: `crc-csi-hostpath-provisioner`
- Prometheus replicas: 1 (dev mode)

## Common Commands

```bash
# Rebuild operator
oc start-build pelorus-operator -n pelorus --from-dir=pelorus-operator --follow

# Rebuild exporters
oc start-build pelorus-exporter -n pelorus --from-dir=exporters --follow

# Restart operator
oc rollout restart deployment/pelorus-operator-controller-manager -n pelorus-operator-system

# Check Prometheus data
oc exec -n pelorus prometheus-prometheus-pelorus-0 -c prometheus -- \
  promtool query instant http://localhost:9090 'count(deploy_timestamp)'

# Seed demo data
./demo/seed-metrics.sh

# Clear metrics
./demo/clear-metrics.sh
```

## Troubleshooting

### Historical Backfill Data Not Queryable (MOST COMMON)

**Symptom**: Seed script completes successfully, TSDB blocks created, but queries return no data for historical time ranges.

**Root Cause**: Out-of-order ingestion disabled or Prometheus Operator too old.

**Solution**:
1. **Check Prometheus Operator version**:
   ```bash
   oc get csv -n pelorus | grep prometheus
   # Need v0.59.0 or higher
   ```

2. **Verify OOO configuration applied**:
   ```bash
   oc get prometheus prometheus-pelorus -n pelorus -o yaml | grep -A 3 additionalArgs
   # Should show: storage.tsdb.out-of-order-time-window: "180d"
   ```

3. **Check Prometheus container args**:
   ```bash
   oc get pod prometheus-prometheus-pelorus-0 -n pelorus \
     -o jsonpath='{.spec.containers[?(@.name=="prometheus")].args}' | grep out-of-order
   # Should include: --storage.tsdb.out-of-order-time-window=180d
   ```

4. **Query Prometheus config**:
   ```bash
   oc port-forward -n pelorus svc/prometheus-pelorus 9090:9091
   curl http://localhost:9090/api/v1/status/config | jq '.data.yaml' | grep outofordertimewindow
   # Should output: outofordertimewindow: 180d (NOT 0)
   ```

**Fix**: If OOO is disabled or operator is too old:
```bash
# Upgrade operator
oc delete subscription prometheus -n pelorus
oc delete csv -n pelorus -l operators.coreos.com/prometheus.pelorus
./demo/install.sh  # Reinstalls with v0.70.0+
```

### Prometheus Pod Restarting
- Check if `prometheus_oauth_cookie_secret` is set in Pelorus CR
- Verify Secret `prometheus-oauth-cookie` exists
- Check operator logs for reconciliation loops

### Metrics Showing Wrong Timestamps (Real-time Scraping)
- Verify `honorTimestamps: true` in ServiceMonitor
- Check webhook exporter metrics endpoint includes explicit timestamps
- Query Prometheus directly to check sample timestamps

### Backfill Corruption Errors
- Clean up partial blocks: `oc exec ... -- rm -rf /prometheus/01KRM*`
- Ensure `/prometheus` is writable (PVC mounted)
- Verify `TMPDIR=/prometheus` is set for promtool

### PVC Not Binding
- Check available storage classes: `oc get storageclass`
- Update `prometheus_storage_pvc_storageclass` to match environment
- CRC uses `crc-csi-hostpath-provisioner`, not `gp2`

### Prometheus Operator Pod Fails with SCC Error

**Symptom**: Operator pod fails to create with error mentioning `runAsUser: 65534` and SCC constraints.

**Error Example**:
```
unable to validate against any security context constraint:
provider restricted-v2: .containers[0].runAsUser: Invalid value: 65534:
must be in the ranges: [1000730000, 1000739999]
```

**Root Cause**: The CSV from k8s-operatorhub catalog hardcodes `runAsUser: 65534` which conflicts with OpenShift's namespace UID ranges.

**Solution**: Patch the CSV to remove hardcoded `runAsUser`:
```bash
# Get the CSV name (version may differ)
CSV_NAME=$(oc get csv -n pelorus | grep prometheusoperator | awk '{print $1}')

# Patch to remove runAsUser
oc patch csv $CSV_NAME -n pelorus --type=json \
  -p='[{"op": "remove", "path": "/spec/install/spec/deployments/0/spec/template/spec/securityContext/runAsUser"}]'

# Delete deployment to trigger recreation
oc delete deployment prometheus-operator -n pelorus

# Verify operator starts
oc get pods -n pelorus -l app.kubernetes.io/name=prometheus-operator
```

**Verification**: Check that operator pod is running with OpenShift-assigned UID:
```bash
oc get pod -n pelorus -l app.kubernetes.io/name=prometheus-operator \
  -o jsonpath='{.spec.securityContext.runAsUser}'
# Should output a UID in the namespace range (e.g., 1000730000)
```
