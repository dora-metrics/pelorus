# Installing Pelorus

Assumptions about this lab:

* You have a freshly installed OpenShift cluster
* You have a RHEL-based bastion server on which you can run the provided commands.
  * This bastion server is connected to the internet
  * The appropriate oc client tools are installed
  * You are logged in to the cluster as an admin user on the bastion server

# Installation

The following will walk through the deployment of Pelorus.

## Step 1: Install local dependencies

Install Helm:

    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3

    chmod 700 get_helm.sh

    ./get_helm.sh

Install JQ

    sudo yum install jq
    
Install Ansible (Used for the demo app)

    sudo yum install ansible

## Step 2: Clone the Pelorus repository

    git clone https://github.com/redhat-cop/pelorus.git


## Step 3: Create cluster Admin account to install Pelorus 

This will allow you to log in with the credentials admin/admin

(You can skip this step if you already have a non-system cluster admin user) 

    echo "
    ---
    apiVersion: v1
    data:
      htpasswd:     YWRtaW46JDJ5JDA1JHBxVFlQbkdERUcxUi9OZWlTdGc5bXVockFtdHBIQTlrbkF0LzVnNzB5    N2JRby9zcTlLMW9pCg==
    kind: Secret
    metadata:
      name: htpass-secret
      namespace: openshift-config
    type: Opaque
    ---
    apiVersion: config.openshift.io/v1
    kind: OAuth
    metadata:
      name: cluster
    spec:
      identityProviders:
      - name: my_htpasswd_provider 
        mappingMethod: claim 
        type: HTPasswd
        htpasswd:
          fileData:
            name: htpass-secret
    ---
    apiVersion: rbac.authorization.k8s.io/v1
    kind: ClusterRoleBinding
    metadata:
      name: lab-admins
    roleRef:
      apiGroup: rbac.authorization.k8s.io
      kind: ClusterRole
      name: cluster-admin
    subjects:
    - apiGroup: rbac.authorization.k8s.io
      kind: User
      name: admin
    " | oc apply -f-


## Step 4: Deployment of Pelorus core stack

Pelorus gets installed via helm charts. The first deploys the operators on which Pelorus depends, the second deploys the core Pelorus stack and the third deploys the exporters that gather the data. The below instructions install into a namespace called `pelorus`.

    oc create namespace pelorus
    helm install operators charts/operators --namespace pelorus
    helm install pelorus charts/pelorus --namespace pelorus

In a few seconds, you will see a number of resources get created:

* Prometheus and Grafana operators
* The core Pelorus stack, which includes:
  * A `Prometheus` instance
  * A `Grafana` instance
  * A `ServiceMonitor` instance for scraping the Pelorus exporters.
  * A `GrafanaDatasource` pointing to Prometheus.
  * A set of `GrafanaDashboards`. See the [dashboards documentation](/docs/Dashboards.md) for more details.
* The following exporters:
  * Deploy Time