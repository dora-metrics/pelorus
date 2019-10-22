# Metrics Driven Transformation

This repository contains tooling to help organizations measure Software Delivery and Value Stream metrics.

## Features

* [Software Delivey Metrics Dashboard](#software-delivery-metrics-dashboard)
* Platform Adoption Dashboard (Planned Feature)
* Value Stream Metrics Dashboard (Planned Feature)

### Software Delivery Metrics Dashboard

The Software Delivery Metrics Dashboard is a Grafana dashboard that can easily be deployed to an OpenShift cluster, and provides and organizational level view of

![Software Delivery Metrics Dashboard](media/sdm-dashboard.png)

## Installation

The following will walk through the deployment of the MDT tooling.

### Prerequisites

Before deploying the tooling, you must have the following prepared

* An OpenShift 3.11 or higher Environment
* A machine from which to run the install (usually your laptop)
  * The OpenShift Command Line Tool (oc)
  * Ansible 2.7+

### Deployment Instructions

Execute the following command to provision the tool:

```
# Install dependencies
ansible-galaxy install -r requirements.yml -p galaxy

# Install prerequisite infrastructure
ansible-playbook -i galaxy/openshift-toolkit/custom-dashboards/.applier galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e include_tags=infrastructure  -e dashboard_namespace=<desired namespace>

# Deploy MDT Tool
ansible-playbook -i .applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml  -e dashboard_namespace=<desired namespace>
```

### Cleaning Up

If you would like to undo the changes above:

```
# Install prerequisite infrastructure
ansible-playbook -i galaxy/openshift-toolkit/custom-dashboards/.applier galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e include_tags=infrastructure -e provision=false -e dashboard_namespace=<namespace dashboard is in>

# Deploy MDT Tool
ansible-playbook -i .applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e provision=false -e dashboard_namespace=<namespace dashboard is in>
```
