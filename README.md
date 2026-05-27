# Pelorus

Pelorus measures software delivery performance using the four DORA metrics: Lead Time for Change, Deployment Frequency, Mean Time to Restore, and Change Failure Rate.

[![Python Linting](https://github.com/dora-metrics/pelorus/actions/workflows/python-linting.yml/badge.svg)](https://github.com/dora-metrics/pelorus/actions)
[![Unit tests](https://github.com/dora-metrics/pelorus/actions/workflows/unittests.yml/badge.svg)](https://github.com/dora-metrics/pelorus/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Prerequisites

- OpenShift 4.20+ (CRC: 6 CPUs, 16GB RAM, 50GB disk) or Kubernetes 1.33+ cluster
- [Helm](https://helm.sh/docs/intro/install/) v3+
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (for development only)

### Operator Dependencies

Pelorus requires a Prometheus operator and a Grafana operator. The install script handles this automatically:

| Component | Source | Notes |
|---|---|---|
| Prometheus Operator | Community Operators | Manages Pelorus' own Prometheus instance |
| Grafana Operator | Community Operators (or COO on OpenShift) | Manages Grafana dashboards and datasources |

On OpenShift with cluster monitoring enabled, the install script also enables user workload monitoring and installs the Cluster Observability Operator (COO).

## Quick Start

```bash
# Build + install everything on OpenShift (auto-detects operator source)
./demo/install.sh

# Or customize the install
OPERATOR_SOURCE=community OAUTH_ENABLED=false ./demo/install.sh

# Seed sample DORA metrics for 4 applications
oc port-forward -n pelorus svc/webhook-exporter 18080:8080 &
./demo/seed-metrics.sh http://localhost:18080
```

OAuth proxy is enabled by default. Grafana uses OpenShift SSO login. Set `OAUTH_ENABLED=false` for basic username/password auth.

The install script:
1. Creates the `pelorus` namespace
2. Installs the required operators
3. Builds exporter and operator images on OpenShift
4. Deploys the Pelorus operator
5. Creates a Pelorus CR with all 4 exporters using the locally built images

## Building the Exporter Image

All exporters share a single container image. Build it before deploying:

```bash
# Docker / Podman
docker build -t pelorus-exporter:latest -f exporters/Containerfile exporters/

# OpenShift (binary build)
oc new-project pelorus
oc new-build --name=pelorus-exporter --strategy=docker --binary -n pelorus
oc start-build pelorus-exporter --from-dir=exporters --follow -n pelorus
```

The `APP_FILE` environment variable selects which exporter runs:

| Exporter | `APP_FILE` |
|---|---|
| Deploy Time | `deploytime/app.py` |
| Commit Time | `committime/app.py` |
| Failure | `failure/app.py` |
| Webhook | `webhook/app.py` |

## Building the Operator Image

The Pelorus operator is a Helm-based operator built with the Operator SDK. Build it before deploying with `make deploy`:

```bash
# Docker / Podman
docker build -t pelorus-operator:latest -f pelorus-operator/Dockerfile pelorus-operator/

# OpenShift (binary build)
oc new-build --name=pelorus-operator --strategy=docker --binary -n pelorus
oc start-build pelorus-operator --from-dir=pelorus-operator --follow -n pelorus
```

## Deploying with Helm

```bash
# Using default values
helm install pelorus pelorus-operator/helm-charts/pelorus -n pelorus

# With custom exporter image (e.g. locally built on OpenShift)
REGISTRY="image-registry.openshift-image-registry.svc:5000"
helm install pelorus pelorus-operator/helm-charts/pelorus -n pelorus \
  --set "exporters.instances[0].app_name=deploytime-exporter" \
  --set "exporters.instances[0].exporter_type=deploytime" \
  --set "exporters.instances[0].image_name=${REGISTRY}/pelorus/pelorus-exporter:latest" \
  --set "exporters.instances[1].app_name=committime-exporter" \
  --set "exporters.instances[1].exporter_type=committime" \
  --set "exporters.instances[1].image_name=${REGISTRY}/pelorus/pelorus-exporter:latest" \
  --set "exporters.instances[2].app_name=webhook-exporter" \
  --set "exporters.instances[2].exporter_type=webhook" \
  --set "exporters.instances[2].image_name=${REGISTRY}/pelorus/pelorus-exporter:latest"

# Without OAuth proxy (simpler for dev/testing)
helm install pelorus pelorus-operator/helm-charts/pelorus -n pelorus \
  --set oauth_proxy_enabled=false
```

### Key Helm Values

| Value | Description | Default |
|---|---|---|
| `oauth_proxy_enabled` | Enable OAuth proxy sidecars | `true` |
| `prometheus_retention` | Data retention period | `1y` |
| `prometheus_storage` | Enable PVC for Prometheus | `false` |
| `exporters.instances` | List of exporter instances | all 4 exporters |
| `exporters.instances[].image_name` | Override container image for an exporter | quay.io default |

## Deploying with the Operator

```bash
cd pelorus-operator
make deploy IMG=quay.io/pelorus/pelorus-operator:0.0.11

# Or with a locally built operator image on OpenShift
REGISTRY="image-registry.openshift-image-registry.svc:5000"
make deploy IMG="${REGISTRY}/pelorus/pelorus-operator:latest"
```

Then create a Pelorus CR:

```bash
oc apply -n pelorus -f - <<EOF
apiVersion: charts.pelorus.dora-metrics.io/v1alpha1
kind: Pelorus
metadata:
  name: pelorus
spec:
  exporters:
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
        image_name: ${REGISTRY}/pelorus/pelorus-exporter:latest
      - app_name: committime-exporter
        exporter_type: committime
        image_name: ${REGISTRY}/pelorus/pelorus-exporter:latest
      - app_name: webhook-exporter
        exporter_type: webhook
        image_name: ${REGISTRY}/pelorus/pelorus-exporter:latest
      - app_name: failuretime-exporter
        exporter_type: failure
        image_name: ${REGISTRY}/pelorus/pelorus-exporter:latest
EOF
```

## Demo

```bash
# Seed sample DORA metrics for 4 applications
./demo/seed-metrics.sh

# Interactive live demo (builds real app, shows metrics capture)
./demo/live-demo.sh
```

See [demo/README.md](demo/README.md) for details.

## Supported Integrations

**Commit Time:** GitHub, GitLab, Bitbucket, Gitea, Azure DevOps, Container Image labels

**Failure Time:** Jira, GitHub Issues, ServiceNow, PagerDuty, Azure DevOps

See [mocks/README.md](mocks/README.md) for mock server testing.
