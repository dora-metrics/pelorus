
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
git clone --depth 1 --branch v2.0.1 https://github.com/konveyor/pelorus
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
    * A set of `GrafanaDashboards`. See the [Outcomes (Dashboards) documentation](philosophy/outcomes/index.md) for more details.
* The following exporters:
    * Deploy Time

From here, some additional configuration is required in order to deploy other exporters, and make the Pelorus

See the [Configuration Guide](Configuration.md) for more information on exporters.

You may additionally want to enabled other features for the core stack. Read on to understand those options.

## Customizing Pelorus

See [Configuring the Pelorus Stack](Configuration.md) for a full readout of all possible configuration items. The following sections describe the  most common supported customizations that can be made to a Pelorus deployment.

### Configure Prometheus Retention

For detailed information about planning Prometheus storage capacity and configuration options please refer to the [operational aspects](https://prometheus.io/docs/prometheus/latest/storage/#operational-aspects) of the Prometheus documentation.

Prometheus is removing data older than 1 year, so if the metric you are interested in happened to be older than 1 year it won't be visible. This is configurable in the `values.yaml` file with the following option:

```yaml
prometheus_retention: 1y
```

Additionally user have option to configure maximum size of storage to be used by Prometheus. The oldest data will get removed first if over that limit. If the data is within retention time but over retention size it will also be removed:

```yaml
prometheus_retention_size: 1GB
```

### Configure Prometheus Persistent Volume (Recommended)

Unlike ephemeral volume that have a lifetime of a pod, persistent volume allows to withstand container restarts or crashes making Prometheus data resilient to such situations.
Pelorus chart allows to use underlying [Prometheus Operator Storage](https://github.com/prometheus-operator/prometheus-operator/blob/main/Documentation/user-guides/storage.md#storage-provisioning-on-aws) capabilities by using prerequisite Kubernetes [`StorageClass`](https://kubernetes.io/docs/concepts/storage/storage-classes/).

It is recommended to use Prometheus Persistent Volume together with the [Long Term Storage](#configure-long-term-storage-recommended).

To install or upgrade helm chart with PVC that uses default StorageClass and default 2Gi capacity, use one additional field in the `values.yaml` file:

```yaml
prometheus_storage: true
# prometheus_storage_pvc_capacity: "<PVC requested volume capacity>" # Optional, default 2Gi
# prometheus_storage_pvc_storageclass: "<your storage class name>"   # Optional, default "gp2"
```

Then run `helm upgrade` with updated `values.yaml` configuration:

```shell
helm upgrade pelorus charts/pelorus --namespace pelorus --values values.yaml
```

To ensure PVC were properly created and Bound to the PV:
```shell
oc get pvc --namespace pelorus
```

### Configure Long Term Storage (Recommended)

The Pelorus chart supports deploying a thanos instance for long term storage.  It can use any S3 bucket provider. The following is an example of configuring a values.yaml file for NooBaa with the local s3 service name:

```
bucket_access_point: s3.pelorus.svc:443
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
```

The default bucket name is thanos.  It can be overriden by specifying an additional value for the bucket name as in:

```
bucket_access_point: s3.pelorus.svc:443
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
thanos_bucket_name: <bucket name here>
```

Then run `helm upgrade` with updated `values.yaml` configuration:

```
helm upgrade pelorus charts/pelorus --namespace pelorus --values values.yaml
```

If you don't have an object storage provider, we recommend [NooBaa](https://www.noobaa.io/) as a free, open source option. You can follow our [NooBaa quickstart](Noobaa.md) to host an instance on OpenShift and configure Pelorus to use it.

### Deploying Across Multiple Clusters

By default, this tool will pull in data from the cluster in which it is running. The tool also supports collecting data across mulitple OpenShift clusters. In order to do this, the thanos sidecar can be configured to read from a shared S3 bucket accross clusters. See [Pelorus Multi-Cluster Architecture](Architecture.md) for details. You define exporters for the desired meterics in each of the clusters which metrics will be evaluated.  The main cluster's Grafana dashboard will display a combined view of the metrics collected in the shared S3 bucket via thanos.

#### Configure Production Cluster.

The produciton configuration example with one deploytime exporter, which uses AWS S3 bucket and AWS volume for Prometheus and tracks deployments to production:

```
bucket_access_point: s3.us-east-2.amazonaws.com
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
thanos_bucket_name: <bucket name here>

prometheus_storage: true
prometheus_storage_pvc_capacity: 20Gi
prometheus_storage_pvc_storageclass: "gp2"

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

```shell
helm uninstall pelorus --namespace pelorus
helm uninstall operators --namespace pelorus

# If Pelorus was deployed with PVCs, you may want to delete them,
# because helm uninstall will not remove PVCs
oc get pvc -n pelorus
oc delete pvc --namespace pelorus \
    prometheus-prometheus-pelorus-db-prometheus-prometheus-pelorus-0 \
    prometheus-prometheus-pelorus-db-prometheus-prometheus-pelorus-1
```
