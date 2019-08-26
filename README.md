# Metrics Driven Transormation Quickstart

Assets to rapidly demonstrate Metrics Driven Transformation (MDT) on the OpenShift Container Platform

## Prerequisites

* Ansible 2.7+
* OpenShift Environment
* OpenShift Command Line Tool

## Provision

Execute the following command to provision the environment:

```
# Install dependencies
ansible-galaxy install -r requirements.yml -p galaxy

# Install prerequisite infrastructure
ansible-playbook -i galaxy/openshift-toolkit/custom-dashboards/.appler galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e include_tags=infrastructure

# Deploy MDT Tool
ansible-playbook -i .applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml
```
