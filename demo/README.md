# Pelorus Demo

Scripts for deploying Pelorus and demonstrating DORA metrics capture.

## Quick Start (OpenShift)

```bash
# 1. Install Pelorus (builds images, deploys operator)
./demo/install.sh

# 2. Seed sample metrics for 4 teams
oc port-forward -n pelorus svc/webhook-exporter 18080:8080 &
./demo/seed-metrics.sh http://localhost:18080

# 3. Open Grafana (wait ~60s for Prometheus to scrape)
#    Route: https://grafana-route-pelorus.apps-crc.testing
#    Login: OpenShift SSO (default) or admin/$PELORUS_PASSWORD (OAUTH_ENABLED=false)
#    Time range: Last 5 minutes
```

## Scripts

| Script | Purpose |
|---|---|
| `install.sh` | Full install: namespace, operators, image builds, operator deploy, Pelorus CR |
| `seed-metrics.sh` | Seeds 4 apps with realistic DORA metrics via webhook exporter |
| `live-demo.sh` | Builds a real app from source and shows metrics capture |
| `run-demo.sh` | Interactive Helm-based demo |
| `demo-tekton.sh` | Tekton pipeline demo (requires OpenShift Pipelines) |

## Seed Metrics

`seed-metrics.sh` creates two waves of data for 4 applications with different performance profiles:

| Application | Lead Time | Failure Rate | Profile |
|---|---|---|---|
| frontend | ~35s | ~10% | Elite performer |
| api-gateway | ~3-4 min | ~22% | Medium performer |
| inventory-service | ~7-8 min | ~15% | Improving |
| payment-service | ~13 min | ~40% | Struggling |

The two-wave approach (data at ~20 min ago and ~5 min ago) ensures Grafana dashboard comparison panels show real change percentages.

## Presales Demo

See [PRESALES-DEMO.md](PRESALES-DEMO.md) for a guided walkthrough with talking points.

## Tekton Pipeline Demo

For an automated pipeline-driven demo on OpenShift with Tekton:

### Prerequisites

- OpenShift cluster with Tekton Pipelines installed
- Fork of the pelorus repo on GitHub

### Setup

```bash
# Create GitHub token secret
oc create secret generic github-secret \
  --from-literal=TOKEN=ghp_<your-token> -n pelorus

# Run the demo
./demo/demo-tekton.sh -g https://github.com/<your-org>/pelorus.git -b binary -r demo_test1

# Automated loop (10 deployments, 5 min apart)
./demo/demo-tekton.sh -g https://github.com/<your-org>/pelorus.git -b binary -r demo_test2 -c 10 -t 5
```

See [tekton-demo-setup/README.md](tekton-demo-setup/README.md) for details.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NAMESPACE` | `pelorus` | Target namespace |
| `OPERATOR_SOURCE` | `auto` | `redhat`, `community`, or `auto` (prefer redhat) |
| `OAUTH_ENABLED` | `true` | Enable OAuth proxy (OpenShift SSO). Set `false` for basic auth |
| `PELORUS_PASSWORD` | random | Grafana admin password (basic auth) / Prometheus htpasswd |
| `TIMEOUT` | `900` | Wait timeout in seconds |
| `WEBHOOK_URL` | auto-detect | Webhook exporter endpoint |
