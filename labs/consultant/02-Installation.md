# Installing Pelorus

## Start Lab Setup

// Get directions from Sha on general Lab setup instructions

## Understand Pelorus Architecture
Link to Architecture

## Install Pelorus via install script
1. Run the following script to install Pelorus.
`oc create namespace pelorus
helm install operators charts/operators --namespace pelorus
helm install pelorus charts/pelorus --namespace pelorus# Installation

The following will walk through the deployment of Pelorus.

## Prerequisites

Before deploying the tooling, we must install the following:

* The OpenShift Command Line Tool (oc)
* [Helm3](https://github.com/helm/helm/releases)
  
* jq

Additionally, if you are planning to use the out of the box exporters to collect Software Delivery data, you will need:

* A [Github Personal Access Token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line)
* A [Jira Personal Access Token](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)

## Initial Deployment

Pelorus gets installed via helm charts. The first deploys the operators on which Pelorus depends, the second deploys the core Pelorus stack and the third deploys the exporters that gather the data. By default, the below instructions install into a namespace called `pelorus`, but you can choose any name you wish.

    oc create namespace pelorus
    helm install operators charts/operators --namespace pelorus
    helm install pelorus charts/pelorus --namespace pelorus

In a few seconds, you will see a number of resourced get created. The above commands will result in the following being deployed:

* Prometheus and Grafana operators
* The core Pelorus stack, which includes:
  * A `Prometheus` instance
  * A `Grafana` instance
  * A `ServiceMonitor` instance for scraping the Pelorus exporters.
  * A `GrafanaDatasource` pointing to Prometheus.
  * A set of `GrafanaDashboards`. See the [dashboards documentation](/docs/Dashboards.md) for more details.
* The following exporters:
  * Deploy Time