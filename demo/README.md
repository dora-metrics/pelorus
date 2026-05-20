# Pelorus Demo

Scripts for deploying Pelorus and demonstrating DORA metrics capture.

## Quick Start (OpenShift)

```bash
# 1. Install Pelorus (builds images, deploys operator)
./demo/install.sh

# 2. (Optional) Clear existing metrics before seeding fresh data
oc port-forward -n pelorus svc/prometheus 19090:9090 &
./demo/clear-metrics.sh http://localhost:19090

# 3. Seed sample metrics for 4 teams over 6 months
oc port-forward -n pelorus svc/webhook-exporter 18080:8080 &
./demo/seed-metrics.sh http://localhost:18080

# 4. Open Grafana (wait ~60s for Prometheus to scrape)
#    Route: https://grafana-route-pelorus.apps-crc.testing
#    Login: OpenShift SSO (default) or admin/$PELORUS_PASSWORD (OAUTH_ENABLED=false)
#    Time range: Last 90 days
```

## Scripts

| Script | Purpose |
|---|---|
| `install.sh` | Full install: namespace, operators, image builds, operator deploy, Pelorus CR |
| `seed-metrics.sh` | Seeds 4 apps with realistic DORA metrics via webhook exporter |
| `clear-metrics.sh` | Clears all Pelorus metrics from Prometheus (useful before re-seeding) |
| `live-demo.sh` | Builds a real app from source and shows metrics capture |
| `run-demo.sh` | Interactive Helm-based demo |
| `demo-tekton.sh` | Tekton pipeline demo (requires OpenShift Pipelines) |

## Seed Metrics

`seed-metrics.sh` creates 6 months of historical data for 4 applications with different performance profiles:

| Application | Lead Time | Deploy Freq | Profile |
|---|---|---|---|
| frontend | 25s (improving) | ~30/month | Elite performer - trunk-based dev, feature flags |
| api-gateway | 3min (was 15min) | 8→20/month | Medium performer - post-monolith migration, improving |
| payment-service | 25min (worsening) | 8→5/month | Low performer - tech debt accumulating |
| inventory-service | 3min (was 20min) | 5→20/month | Turnaround story - dramatic improvement in last 3 months |

This creates realistic trends showing performance changes over time. Set Grafana to "Last 90 days" or "Last 6 months" to see the full history.

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
