# Welcome to Pelorus

![Pelorus](img/Logo-Pelorus-A-Standard-RGB_smaller.png)

![](https://github.com/redhat-cop/pelorus/workflows/Pylama/badge.svg)

Pelorus is a tool that helps IT organizations measure their impact on the overall performance of their organization. It does this by gathering metrics about team and organizational behaviors over time in some key areas of IT that have been shown to impact the value they deliver to the organization as a whole. Some of the key outcomes Pelorus can focus on are:

- Software Delivery Performance
- Product Quality and Sustainability
- Customer experience

For more background on the project you can read @trevorquinn's blog post on [Metrics Driven Transformation](https://www.openshift.com/blog/exploring-a-metrics-driven-approach-to-transformation)

## Software Delivery Performance as an outcome

Currently, Pelorus functionality can capture proven metrics that measure Software Delivery Performance -- a significant outcome that IT organizations aim to deliver.

Pelorus is a Grafana dashboard that can easily be deployed to an OpenShift cluster, and provides an organizational-level view of the [four critical measures of software delivery performance](https://blog.openshift.com/exploring-a-metrics-driven-approach-to-transformation/).

![Software Delivery Metrics Dashboard](img/sdp-dashboard.png)

A short video describing each of these metrics is available [here](https://www.youtube.com/watch?v=7-iB_KhUaQg).

## Prior Knowledge

In order to be successful deploying, managing and consuming Pelorus, the following prior knowledge is required:

* Understanding of Software Development Life Cycle.
* Understanding of [Kubernetes Operators](https://www.redhat.com/en/topics/containers/what-is-a-kubernetes-operator).
* Understanding of [helm](https://helm.sh/).
* Understanding of source version control systems: [Git](https://git-scm.com/).
* Understanding of [OpenShift Builds](https://docs.openshift.com/container-platform/4.6/builds/understanding-image-builds.html) and [Pipelines](https://www.openshift.com/blog/jenkins-pipelines).
* OpenShift administrator knowledge & permissions.
* Understanding of Cloud Native monitoring tools: [Prometheus & Prometheus Exporters](https://prometheus.io/), [Thanos](https://thanos.io/) and [Grafana](https://grafana.com/).
* Understanding of software development project tracking tools: [Jira](https://www.atlassian.com/software/jira).