# Installing Pelorus

Assumptions about this lab:

* You have a freshly installed OpenShift cluster
* You have a RHEL-based bastion server on which you can run the provided commands.
  * This bastion server is connected to the internet
  * You are logged in to the cluster as an admin user

# Installation

The following will walk through the deployment of Pelorus.

## Step 1: Install dependencies


Run the following commands to install dependencies:

Install Helm:

    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3

    chmod 700 get_helm.sh

    ./get_helm.sh

Install JQ

    sudo yum install jq
    
Install Ansible

    sudo yum install ansible

## Step 2: Check out the latest release of Pelorus

Clone the Pelorus repository

    git clone https://github.com/redhat-cop/pelorus.git

    git checkout v1.2.2

    chmod 700 .openshift/create_user.sh


## Step 3: Initial deployment of Pelorus core stack

Pelorus gets installed via helm charts. The first deploys the operators on which Pelorus depends, the second deploys the core Pelorus stack and the third deploys the exporters that gather the data. The below instructions install into a namespace called `pelorus`.



Install helm charts

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