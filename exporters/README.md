# Metrics Exporters

Pelorus exporters collect DORA metrics from various sources and expose them to Prometheus.

Available exporters:

- **committime** — Lead Time for Change (commit to deploy)
- **deploytime** — Deployment Frequency
- **failure** — Mean Time to Restore / Change Failure Rate
- **webhook** — Receives metrics via HTTP webhooks

For deployment and configuration, see the [configuration guide](https://pelorus.readthedocs.io/en/latest/GettingStarted/configuration/PelorusExporters/).
