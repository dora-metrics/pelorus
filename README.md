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
ansible-playbook -i galaxy/openshift-toolkit/custom-dashboards/.applier galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e include_tags=infrastructure

# Deploy MDT Tool
ansible-playbook -i .applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml
```

### Adding extra prometheus instances

Add a extra_prometheus_hosts variable to the '.applier/group_vars/seed_hosts.yml'.  This variable is an array of hashes with the following elements:

* id - a description of the prometheus host (this will be used as a label to select metrics in the federated instance).
* hostname - the fully qualified domain name or ip address of the host with the extra prometheus instance
* password - the password used for the 'internal' basic auth account (this is provided by the k8s metrics prometheus instances in a secret).

For example:

```
extra_prometheus_hosts:
  - id: "ci-1"
    hostname: "prometheus-k8s-openshift-monitoring.apps.example.com"
    password: "<redacted>"

dashboard_namespace: custom-dashboards
openshift_cluster_content:
  - ...
```


### Cleaning Up

If you would like to undo the changes above:

```
# Install prerequisite infrastructure
ansible-playbook -i galaxy/openshift-toolkit/custom-dashboards/.applier galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e include_tags=infrastructure -e provision=false

# Deploy MDT Tool
ansible-playbook -i .applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e provision=false
```