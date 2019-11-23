# Metrics Driven Transformation

This repository contains tooling to help organizations measure Software Delivery and Value Stream metrics.

## Features

* [Software Delivey Metrics Dashboard](#software-delivery-metrics-dashboard)
* Platform Adoption Dashboard (Planned Feature)
* Value Stream Metrics Dashboard (Planned Feature)

### Software Delivery Metrics Dashboard

The Software Delivery Metrics Dashboard is a Grafana dashboard that can easily be deployed to an OpenShift cluster, and provides and organizational level view of the [four critical measures of software delivery performance](https://blog.openshift.com/exploring-a-metrics-driven-approach-to-transformation/).

![Software Delivery Metrics Dashboard](media/sdm-dashboard.png)

## Installation

The following will walk through the deployment of the MDT tooling.

### Prerequisites

Before deploying the tooling, you must have the following prepared

* An OpenShift 3.11 or higher Environment
* A machine from which to run the install (usually your laptop)
  * The OpenShift Command Line Tool (oc)
  * Helm 3

### Deployment Instructions

The following process can be followed to deploy the tool.

First, we must collect some information from the cluster to feed to our templates.

    PROMETHEUS_HTPASSWD_AUTH=$(oc get secret prometheus-k8s-htpasswd -n openshift-monitoring -o jsonpath='{.data.auth}')
    GRAFANA_DATASOURCE_PASSWORD=$(oc get secret grafana-datasources -n openshift-monitoring -o jsonpath='{.data.prometheus\.yaml}' | base64 -d | jq .datasources[0].basicAuthPassword)


    #TODO: Finish data gathering

    helm template --namespace pelorus pelorus ./charts/deploy/ | oc apply -f - -n pelorus

### Adding extra prometheus instances

Edit the extra_prometheus_hosts.yml file.  It is a yaml file with an array of entries with the following parameters:

* id - a description of the prometheus host (this will be used as a label to select metrics in the federated instance).
* hostname - the fully qualified domain name or ip address of the host with the extra prometheus instance
* password - the password used for the 'internal' basic auth account (this is provided by the k8s metrics prometheus instances in a secret).

For example:

    extra_prometheus_hosts:
      - id: "ci-1"
        hostname: "prometheus-k8s-openshift-monitoring.apps.example.com"
        password: "<redacted>"

Once you are finished adding your extra hosts, apply the file as the secret 'extra-prometheus-secrets'.

    oc create secret generic extra-prometheus-secrets --from-file extra_prometheus_hosts.yml

### Cleaning Up

If you would like to undo the changes above:

    # Remove dashboarding stack
    ansible-playbook -i galaxy/openshift-toolkit/custom-dashboards/.applier galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e include_tags=infrastructure -e provision=false

    # Remove Dashboard
    ansible-playbook -i .applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e provision=false
