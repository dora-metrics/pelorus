# Pelorus architecture

The following diagram shows the various components and traffic flows in the Pelorus ecosystem.

## Basic architecture and components

![Pelorus Architecture Diagram](img/architecture.png)

Pelorus is composed of the following open source components:

* Prometheus Operator
  * Prometheus
  * Thanos (backed by Object Store)
* Grafana Operator
  * Grafana
* Pelorus Exporters
  * Commit Time
  * Deploy Time
  * Failure

### Prometheus and Grafana

[Prometheus](https://prometheus.io/) monitors and stores time-series data and [Grafana](https://grafana.com/) provides dashboard visualization of the metrics.  Pelorus is built on these open source tools and focuses on the core differentiators, methods of gathering them, and building information radiators from those metrics.

#### Thanos
[Thanos](https://thanos.io/) is a sub-set of Prometheus components that provide high availability and long term data storage. Thanos gives Pelorus dashboards the ability to look back over months or years of organizational data.

### Pelorus exporters
[Exporters](https://prometheus.io/docs/instrumenting/exporters/) are Prometheus bots that gather and expose data. Pelorus uses the exporter framework to build integrations with common IT systems to gather the relevant dashboard data.

## Multi-cluster architecture (production)
Pelorus typically needs to be installed across multiple Kubernetes clusters in production environments. In most cases, the key clusters are production and the development cluster where builds are happening.

Below is an example of Pelorus Multi-Cluster architecture.

![](img/multi-cluster_architecture.png)
