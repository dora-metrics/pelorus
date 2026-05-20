# Adding OperatorHub.io Catalog Source to OpenShift/CRC

## Overview

The k8s-operatorhub catalog (`quay.io/operatorhubio/catalog:latest`) provides **newer versions** of Prometheus Operator compared to the OpenShift community-operators catalog.

### Version Comparison

| Catalog Source | Prometheus Operator Version | `additionalArgs` Support |
|----------------|----------------------------|--------------------------|
| **community-operators** (OpenShift default) | v0.56.3 (May 2022) | ❌ No (added in v0.59.0) |
| **operatorhubio-catalog** (k8s-operatorhub) | **v0.70.0** (latest) | ✅ **Yes** |

### Available Versions in operatorhubio-catalog

The `beta` channel includes these versions:
- v0.70.0 (current)
- v0.65.1
- v0.47.0
- v0.37.0
- v0.32.0
- v0.27.0
- v0.22.2
- v0.15.0
- v0.14.0

## Installation Steps

### 1. Add the OperatorHub.io Catalog Source

```bash
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: operatorhubio-catalog
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: quay.io/operatorhubio/catalog:latest
  displayName: OperatorHub.io Operators
  publisher: OperatorHub.io
  updateStrategy:
    registryPoll:
      interval: 60m
EOF
```

### 2. Wait for Catalog to Sync

```bash
# Check catalog source status
oc get catalogsource operatorhubio-catalog -n openshift-marketplace

# Wait for packages to appear (may take 30-60 seconds)
oc get packagemanifest -l catalog=operatorhubio-catalog | grep prometheus
```

### 3. Verify Prometheus Operator Version

```bash
oc get packagemanifest prometheus -n openshift-marketplace -o yaml \
  | grep -A 5 "catalogSource: operatorhubio-catalog" \
  | grep "currentCSV"
# Should show: prometheusoperator.v0.70.0
```

### 4. Update Pelorus Installation to Use New Catalog

Modify `demo/install.sh` to specify the new catalog source:

```bash
# In the Subscription section for Prometheus Operator
spec:
  channel: beta
  name: prometheus
  source: operatorhubio-catalog  # Changed from community-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
```

### 5. Upgrade Existing Installation (if applicable)

If you already have Prometheus Operator v0.56.3 installed, you MUST cleanup first:

**Option A: Use the cleanup script (recommended):**
```bash
# Run the automated cleanup script
./demo/cleanup-prometheus.sh

# Then run the install script
./demo/install.sh
```

**Option B: Manual cleanup:**
```bash
# Delete Prometheus CR
oc delete prometheus prometheus-pelorus -n pelorus --wait=true

# Delete old subscription and CSV
oc delete subscription prometheus -n pelorus
oc delete csv prometheusoperator.0.56.3 -n pelorus

# Re-run install script (will use new catalog)
./demo/install.sh
```

**Why cleanup is required:**
- Switching catalog sources mid-flight can cause upgrade issues
- v0.56.3 → v0.70.0 is a large version jump (14 versions)
- Ensures additionalArgs configuration is applied cleanly
- Prevents CRD schema conflicts

## Verification

After installation, verify the operator version and OOO support:

```bash
# Check installed CSV
oc get csv -n pelorus | grep prometheus
# Should show: prometheusoperator.v0.70.0

# Verify additionalArgs in Prometheus CR
oc get prometheus prometheus-pelorus -n pelorus -o yaml | grep -A 3 additionalArgs
# Should show:
# additionalArgs:
# - name: storage.tsdb.out-of-order-time-window
#   value: "180d"

# Verify Prometheus container args
oc get pod prometheus-prometheus-pelorus-0 -n pelorus \
  -o jsonpath='{.spec.containers[?(@.name=="prometheus")].args}' \
  | jq -r '.[]' | grep out-of-order
# Should output: --storage.tsdb.out-of-order-time-window=180d
```

## Benefits

✅ **Prometheus Operator v0.70.0** (vs v0.56.3)
✅ **Out-of-order ingestion support** via `additionalArgs`
✅ **Historical backfill works** with 6-month demo data
✅ **PrometheusAgent CRD** support (v1alpha1)
✅ **Better compatibility** with newer Prometheus versions

## Considerations

### Compatibility
- **OpenShift/OKD**: Fully compatible with OpenShift 4.x OLM
- **CRC**: Works with CodeReady Containers local development
- **Kubernetes**: Also compatible with vanilla Kubernetes + OLM

### Update Strategy
- The catalog polls for updates every 60 minutes
- New operator versions become available automatically
- InstallPlanApproval can be set to `Manual` for controlled upgrades

### Catalog Maintenance
- The `quay.io/operatorhubio/catalog:latest` tag is maintained by the k8s-operatorhub community
- Still lags behind official releases (v0.70.0 vs v0.90.1 upstream)
- For absolute latest versions, consider deploying Prometheus Operator manually

## Troubleshooting

### Catalog Not Syncing
```bash
# Check catalog pod logs
oc get pods -n openshift-marketplace | grep operatorhubio
oc logs -n openshift-marketplace <catalog-pod-name>
```

### Package Not Appearing
```bash
# Force catalog pod restart
oc delete pod -n openshift-marketplace -l olm.catalogSource=operatorhubio-catalog
```

### Subscription Conflicts
If you get conflicts between catalogs:
```bash
# List all packagemanifests for prometheus
oc get packagemanifest prometheus -n openshift-marketplace -o yaml

# Ensure Subscription specifies correct source
oc get subscription prometheus -n pelorus -o yaml | grep source
```

## References

- [k8s-operatorhub/community-operators GitHub](https://github.com/k8s-operatorhub/community-operators)
- [OperatorHub.io - Prometheus Operator](https://operatorhub.io/operator/prometheus)
- [OLM CatalogSource Documentation](https://olm.operatorframework.io/docs/concepts/crds/catalogsource/)
- [Adding OperatorHub.io to OpenShift](https://www.devopsschool.com/blog/openshift-add-all-operatorhub-io-operators-to-openshift/)
