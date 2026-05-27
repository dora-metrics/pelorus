# E2E Tests

End-to-end tests for Pelorus deployment on OpenShift. Both tests build all images directly on OpenShift - no local container engine or external registry required.

## Prerequisites

- OpenShift cluster (CRC or full cluster) with `oc` logged in as admin
- `helm` CLI installed
- Prometheus Operator and Grafana Operator available in OperatorHub

## Tests

### Helm Deploy (`test_helm_deploy.sh`)

Tests the full Helm-based deployment workflow:

1. Creates the `pelorus` namespace
2. Installs Prometheus and Grafana operators from OperatorHub
3. Builds the exporter image on OpenShift (`oc start-build`)
4. Deploys Pelorus via `helm install`
5. Tags Helm-managed ImageStreams with the built exporter image
6. Sends test metrics via the webhook exporter
7. Verifies metrics appear in Prometheus (including recording rules)
8. Verifies Grafana is running
9. Cleans up everything

```bash
./_test/e2e/test_helm_deploy.sh

# Keep resources for debugging
SKIP_CLEANUP=1 ./_test/e2e/test_helm_deploy.sh
```

### Operator Deploy (`test_operator_deploy.sh`)

Tests the operator-based deployment workflow:

1. Creates the `pelorus` namespace
2. Installs Prometheus and Grafana operators from OperatorHub
3. Builds the exporter image on OpenShift
4. Builds the Pelorus Operator image on OpenShift
5. Deploys the operator with `make deploy` using the built image
6. Creates a Pelorus CR with `image_tag` overrides
7. Tags ImageStreams with the built exporter image
8. Verifies the operator reconciles and deploys all components
9. Sends test metrics and verifies end-to-end Prometheus flow
10. Cleans up everything

```bash
./_test/e2e/test_operator_deploy.sh

# Keep resources for debugging
SKIP_CLEANUP=1 ./_test/e2e/test_operator_deploy.sh
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NAMESPACE` | `pelorus` | Namespace to deploy into |
| `CHART_PATH` | `pelorus-operator/helm-charts/pelorus` | Path to Helm chart |
| `TIMEOUT` | `300` | Default wait timeout in seconds |
| `SKIP_CLEANUP` | `0` | Set to `1` to keep resources after test |
