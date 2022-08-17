# Pelorus Dashboards
Pelorus dashboards show Key Performance Indicators (KPIs) that measure various Bridge Outcomes. Learn what we measure and why on the [Our Philosophy](https://github.com/konveyor/konveyor.github.io/blob/main/content/Pelorus/philosophy.md) page.

## Terminology
Below are some common terms to better understand Pelorus.

**Exporters**

Exporters enable Pelorus to customize data points to capture metrics from various providers including:
* Deploy Time Exporter
* Commit Time Exporter
* Failure Time Exporter

**Providers**

The source from which exporters automate collection of data points (metrics) including:
* OpenShift
* Git providers (GitHub, GitLab, Bitbucket)
* Issue trackers (JIRA, ServiceNow)

**Metrics**

The data points that are collected from the providers including:
* deploy_time
* commit_time
* failure_creation
* failure_resolution

**Measures**

Metrics calculated to represent an outcome. Each outcome is made measurable by a set of representative measures including:
* Lead Time for Change
* Deployment Frequency
* Mean Time to Restore
* Change Failure Rate

## Dashboards Index

* [Software Delivery Performance](dashboards/SoftwareDeliveryPerformance.md)
* Value Flow (Coming Soon)
* Supported Technology Adoption (Coming Soon)
* Availability (Coming Soon)
