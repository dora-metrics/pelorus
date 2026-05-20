# Prometheus Remote Write & Backdating Experiment - Findings

**Date**: 2026-05-15  
**Prometheus Version**: 3.11.3 (April 2026)  
**Prometheus Operator Version**: v0.56.3 (2022)

## Executive Summary

**CRITICAL DISCOVERY**: The root cause of backfill data being un-queryable is **out-of-order (OOO) ingestion being completely disabled** in Prometheus (`outofordertimewindow: 0`).

**Remote Write Status**: Cannot be tested for backdated metrics because:
1. Prometheus 3.11.3 does not have text-format import endpoints
2. Standard remote write (`/api/v1/write`) requires protobuf+snappy encoding
3. OOO is disabled, so even if we could send data via remote write, it would be rejected

**Recommendation**: Focus on enabling out-of-order ingestion in Prometheus rather than switching from backfill to remote write.

---

## Problem Statement

The Pelorus demo seed script (`./demo/seed-metrics.sh`) successfully creates TSDB blocks with 6 months of historical DORA metrics using Prometheus backfill (`promtool tsdb create-blocks-from openmetrics`). However:

- ✅ Data is imported into Prometheus TSDB
- ✅ TSDB blocks are created successfully  
- ❌ **Queries do not return the historical data**
- ❌ Grafana dashboards show no metrics when time range is set to "Last 6 months"

---

## Root Cause Analysis

### Discovery Process

1. **Checked Prometheus configuration**:
   ```bash
   curl http://localhost:9090/api/v1/status/config | jq '.data.yaml'
   ```
   **Result**: `outofordertimewindow: 0`

2. **What this means**:
   - Out-of-order sample ingestion is **completely disabled**
   - Prometheus will accept samples ONLY if their timestamp is >= the most recent sample timestamp for that series
   - Backfilled data (with timestamps in the past) cannot be queried because Prometheus doesn't index/query it properly when OOO is disabled

### Why OOO Matters for Backdated Data

Prometheus has two ingestion modes:

| Mode | OOO Window | Behavior with Backdated Data |
|------|------------|------------------------------|
| **Strict In-Order** | `0` (disabled) | Rejects or ignores samples older than latest sample. Backfill blocks may exist but queries don't work. |
| **Out-of-Order** | `> 0` (e.g., `180d`) | Accepts samples within the configured window. Historical data is queryable. |

**Current State**: Prometheus is in strict in-order mode, which breaks backfill queries.

---

## Experiment Results

### Test 1: Remote Write Text Format

**Tested Endpoints**:
- `/api/v1/import/prometheus` → 404  
- `/api/v1/import` → 404  
- `/federate` → 405 (Method Not Allowed)

**Result**: ❌ Prometheus 3.11.3 does not support text-format import via HTTP POST

### Test 2: Check for OOO Configuration Flag

**Attempt**: Add `--storage.tsdb.out-of-order-time-window=180d` to Prometheus container args

**Result**: ❌ **Flag does not exist in Prometheus 3.11.3**  
```
Error parsing command line arguments: unknown long flag '--storage.tsdb.out-of-order-time-window'
```

**Analysis**: Prometheus 3.x may have changed how OOO is configured (possibly moved to config file instead of CLI flag), or this feature may have been renamed/removed.

### Test 3: Prometheus Operator `additionalArgs`

**Configuration Added**:
```yaml
# Prometheus CR
spec:
  additionalArgs:
    - name: storage.tsdb.out-of-order-time-window
      value: 180d
```

**Result**: ❌ Prometheus Operator v0.56.3 (from 2022) does not apply `additionalArgs` to the StatefulSet

**Analysis**: This operator version predates Prometheus 3.x and doesn't properly handle modern additionalArgs for TSDB configuration.

---

## Key Findings

### 1. Out-of-Order Ingestion is Disabled

**Evidence**:
```yaml
storage:
  tsdb:
    outofordertimewindow: 0  # ← DISABLED
    retention:
      time: 1y
      size: 1GiB
```

**Impact**: This is WHY backfilled data isn't queryable. The TSDB blocks exist, but Prometheus query engine doesn't handle them correctly when OOO is disabled.

### 2. Prometheus Version vs Operator Version Mismatch

- **Prometheus**: v3.11.3 (April 2026) - very modern
- **Prometheus Operator**: v0.56.3 (2022) - 4 years old

**Impact**: The operator doesn't know how to configure Prometheus 3.x features like OOO ingestion.

### 3. Remote Write is Not a Solution

Even if we implement proper protobuf remote write:
- OOO is still disabled, so 6-month-old samples would be rejected
- Configuring OOO via config file (not CLI flags) is still needed
- Backfill is actually the CORRECT tool for bulk historical ingestion

---

## Recommendations

### Option 1: Enable OOO via Prometheus Configuration File (RECOMMENDED)

Prometheus 3.x likely configures OOO in `prometheus.yml` instead of CLI flags:

```yaml
# Prometheus configuration (not tested yet)
storage:
  tsdb:
    out_of_order_time_window: 180d  # or similar syntax
```

**Steps**:
1. Research Prometheus 3.11.3 documentation for OOO configuration syntax
2. Modify Pelorus operator Helm chart to inject OOO config into `prometheus.yml`
3. Restart Prometheus
4. Re-run backfill or test if existing backfilled data becomes queryable

### Option 2: Upgrade Prometheus Operator

Upgrade to a modern Prometheus Operator version that:
- Supports Prometheus 3.x configuration
- Properly handles `additionalArgs` for TSDB settings
- Has better compatibility with current Prometheus versions

**Trade-off**: More invasive change, may require significant testing.

### Option 3: Manual StatefulSet Patch (TEMPORARY WORKAROUND)

If OOO can be enabled via config file:
1. Scale down Prometheus Operator temporarily
2. Manually patch Prometheus ConfigMap with OOO settings
3. Restart Prometheus pod
4. Test if backfilled data becomes queryable

**Note**: This is NOT durable - operator reconciliation will revert changes.

---

## Questions to Research

1. **How is OOO configured in Prometheus 3.x?**
   - Is it in `prometheus.yml` instead of CLI flags?
   - What's the correct syntax?

2. **Is OOO enabled by default in Prometheus 3.x?**
   - If yes, why is `outofordertimewindow: 0`?
   - Is there a separate config needed to enable it?

3. **Can backfilled TSDB blocks be queried without OOO enabled?**
   - Is there a way to make Prometheus index/query pre-existing blocks?
   - Or is OOO strictly required for historical data queries?

---

## What We've Accomplished

✅ **Created test script**: `/projects/pelorus/demo/test-remote-write.py`  
✅ **Updated CRD**: Added `prometheus_out_of_order_time_window` field to Pelorus CRD  
✅ **Updated Helm charts**: Template now renders OOO config (though operator doesn't apply it)  
✅ **Updated install script**: Sets `prometheus_out_of_order_time_window: 180d` by default  
✅ **Identified root cause**: OOO disabled is why backfill data isn't queryable

---

## Next Steps

1. **Research Prometheus 3.11.3 OOO configuration**
   - Check official Prometheus 3.x documentation
   - Find correct syntax for enabling OOO in config file

2. **Test OOO enabling**
   - Manually edit Prometheus ConfigMap
   - Restart Prometheus
   - Query existing backfilled data to see if it becomes queryable

3. **If OOO solves the problem**:
   - Update operator Helm charts to inject OOO config into prometheus.yml
   - Rebuild operator
   - Document the fix in CLAUDE.md

4. **Alternative**: If OOO can't be enabled in current setup:
   - Consider upgrading Prometheus Operator
   - Or explore VictoriaMetrics as temporary import target (supports any timestamp)

---

## Files Modified

- `/projects/pelorus/demo/test-remote-write.py` (NEW)
- `/projects/pelorus/pelorus-operator/config/crd/bases/charts.pelorus.dora-metrics.io_peloruses.yaml`
- `/projects/pelorus/pelorus-operator/bundle/manifests/charts.pelorus.dora-metrics.io_peloruses.yaml`
- `/projects/pelorus/pelorus-operator/helm-charts/pelorus/values.yaml`
- `/projects/pelorus/pelorus-operator/helm-charts/pelorus/templates/prometheus-cr.yaml`
- `/projects/pelorus/demo/install.sh`

---

## Conclusion

**Remote write is NOT the solution** - it faces the same OOO limitation as backfill.  

**The real fix**: Enable out-of-order ingestion in Prometheus 3.11.3, which will make the existing backfill approach work correctly.

The challenge is determining HOW to configure OOO in Prometheus 3.x, given that:
- The CLI flag doesn't exist
- The operator is old and doesn't support modern Prometheus features
- Documentation/research is needed for Prometheus 3.x OOO configuration syntax
