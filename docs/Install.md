
# Installation

The following will walk through the deployment of Pelorus.

## Prerequisites

Before deploying the tooling, you must have the following prepared

* An OpenShift 4.7 or higher Environment
* A machine from which to run the install (usually your laptop)
  * The OpenShift Command Line Tool (oc)
  * [Helm3](https://github.com/helm/helm/releases)
  * jq
  * git

## Initial Deployment

Pelorus gets installed via helm charts. The first deploys the operators on which Pelorus depends, the second deploys the core Pelorus stack and the third deploys the exporters that gather the data. By default, the below instructions install into a namespace called `pelorus`, but you can choose any name you wish.

```shell
# clone the repo (you can use a different release or clone from master if you wish)
git clone --depth 1 --branch v1.7.1 https://github.com/konveyor/pelorus
cd pelorus
oc create namespace pelorus
helm install operators charts/operators --namespace pelorus
# Verify the operators are completely installed before installing the pelorus helm chart
helm install pelorus charts/pelorus --namespace pelorus
```

In a few seconds, you will see a number of resourced get created. The above commands will result in the following being deployed:

* Prometheus and Grafana operators
* The core Pelorus stack, which includes:
    * A `Prometheus` instance
    * A `Grafana` instance
    * A `ServiceMonitor` instance for scraping the Pelorus exporters.
    * A `GrafanaDatasource` pointing to Prometheus.
    * A set of `GrafanaDashboards`. See the [dashboards documentation](Dashboards.md) for more details.
* The following exporters:
    * Deploy Time

From here, some additional configuration is required in order to deploy other exporters, and make the Pelorus

See the [Configuration Guide](Configuration.md) for more information on exporters.

You may additionally want to enabled other features for the core stack. Read on to understand those options.

## Customizing Pelorus

See [Configuring the Pelorus Stack](Configuration.md) for a full readout of all possible configuration items. The following sections describe the  most common supported customizations that can be made to a Pelorus deployment.

### Configure Long Term Storage (Recommended)

The Pelorus chart supports deploying a thanos instance for long term storage.  It can use any S3 bucket provider. The following is an example of configuring a values.yaml file for NooBaa with the local s3 service name:

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

Then run `helm upgrade` with updated `values.yaml` configuration:

```
helm upgrade pelorus charts/deploy --namespace pelorus --values values.yaml
```

If you don't have an object storage provider, we recommend [NooBaa](https://www.noobaa.io/) as a free, open source option. You can follow our [NooBaa quickstart](Noobaa.md) to host an instance on OpenShift and configure Pelorus to use it.

### Deploying Across Multiple Clusters

By default, this tool will pull in data from the cluster in which it is running. The tool also supports collecting data across mulitple OpenShift clusters. In order to do this, the thanos sidecar can be configured to read from a shared S3 bucket accross clusters. See [Pelorus Multi-Cluster Architecture](Architecture.md) for details. You define exporters for the desired meterics in each of the clusters which metrics will be evaluated.  The main cluster's Grafana dashboard will display a combined view of the metrics collected in the shared S3 bucket via thanos.

#### Configure Production Cluster.

The produciton configuration example with one deploytime exporter, which uses AWS S3 bucket and tracks deployments to production:

```
bucket_access_point: s3.us-east-2.amazonaws.com
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
thanos_bucket_name: <bucket name here>```

deployment:
  labels:
    app.kubernetes.io/component: production
    app.kubernetes.io/name: pelorus
    app.kubernetes.io/version: v0.33.0

exporters:
  instances:
  - app_name: deploytime-exporter
    exporter_type: deploytime
    env_from_configmaps:
    - pelorus-config
    - deploytime-config
```


## Uninstalling

Cleaning up Pelorus is very simple.

    helm uninstall pelorus --namespace pelorus
    helm uninstall operators --namespace pelorus

