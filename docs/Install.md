
# Installation

The following will walk through the deployment of Pelorus.

## Prerequisites

Before deploying the tooling, you must have the following prepared

* An OpenShift 3.11 or higher Environment
* A machine from which to run the install (usually your laptop)
  * The OpenShift Command Line Tool (oc)
  * [Helm3](https://github.com/helm/helm/releases)
  * jq

Additionally, if you are planning to use the out of the box exporters to collect Software Delivery data, you will need:

* A [Github Personal Access Token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line)
* A [Jira Personal Access Token](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)

## Initial Deployment

Pelorus gets installed via helm charts. The first deploys the operators on which Pelorus depends, the second deploys the core Pelorus stack and the third deploys the exporters that gather the data. By default, the below instructions install into a namespace called `pelorus`, but you can choose any name you wish.

1. Deploy the Pelorus stack

        oc create namespace pelorus
        helm install operators charts/operators --namespace pelorus
        helm install pelorus charts/pelorus --namespace pelorus

    In a few seconds, you will see a number of resourced get created.
2. Create the exporter secrets
    1. For Github

            oc create secret generic github-secret --from-literal=GITHUB_USER=<username> --from-literal=GITHUB_TOKEN=<personal access token> -n pelorus
    2. For Jira

            oc create secret generic jira-secret --from-literal=SERVER=<Jira Server> --from-literal=USER=<username> --from-literal=TOKEN=<personal access token> --from-literal=PROJECT=<Jira Project> -n pelorus
3. Deploy Exporters

        helm template charts/exporter/ -f exporters/committime/values.yaml --namespace pelorus | oc apply -f- -n pelorus
        helm template charts/exporter/ -f exporters/deploytime/values.yaml --namespace pelorus | oc apply -f- -n pelorus
        helm template charts/exporter/ -f exporters/failure/values.yaml --namespace pelorus | oc apply -f- -n pelorus

See the [Configuration Guide](/docs/Configuration.md) for more information on exporters.

## Customizing Pelorus

See [Configuring the Pelorus Stack](/docs/Configuration.md) for a full readout of all possible configuration items. The following sections describe the  most common supported customizations that can be made to a Pelorus deployment.

### Configure Long Term Storage

The Pelorus chart supports deploying a thanos instance for long term storage.  It can use any S3 bucket provider. The following is an example of configuring a values.yaml file for noobaa with the local s3 service name:

```
bucket_access_point: s3.noobaa.svc
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
```

The default bucket name is thanos.  It can be overriden by specifying an additional value for the bucket name as in:

```
bucket_access_point: s3.noobaa.svc
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
thanos_bucket_name: <bucket name here>
```

Then pass this to runhelm.sh like this:

```
helm upgrade pelorus charts/deploy --namespace pelorus --values values.yaml
```

If you don't have an object storage provider, we recommend [MinIO](https://min.io/) as a free, open source option. You can follow our [MinIO quickstart](/docs/MinIO.md) to host an instance on OpenShift and configure Pelorus to use it.

### Deploying Across Multiple Clusters

By default, this tool will pull in data from the cluster in which it is running. The tool also supports collecting data across mulitple OpenShift clusters. In order to do this, we need to point the Pelorus instance at these other clusters.

To do this, create a new variables file , `extra_prometheus_hosts.yaml`.  It is a yaml file with an array of entries with the following parameters:

* id - a description of the prometheus host (this will be used as a label to select metrics in the federated instance).
* hostname - the fully qualified domain name or ip address of the host with the extra prometheus instance
* password - the password used for the 'internal' basic auth account (this is provided by the k8s metrics prometheus instances in a secret).

For example:

    extra_prometheus_hosts:
      - id: "ci-1"
        hostname: "prometheus-k8s-openshift-monitoring.apps.ci-1.example.com"
        password: "<redacted>"

Once you are finished adding your extra hosts, you can update your stack by re-running the helm command above, passing your values file with `--values extra-prometheus-hosts.yaml`

```
helm upgrade pelorus charts/deploy --namespace pelorus -v extra-prometheus-hosts.yaml
```

## Uninstalling

Cleaning up Pelorus is very simple.

    helm uninstall pelorus --namespace pelorus
    helm uninstall operators --namespace pelorus

