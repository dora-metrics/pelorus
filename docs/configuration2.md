# Customizing Pelorus

See [Configuring the Pelorus Stack](Configuration.md) for a full readout of all possible configuration items. The following sections describe the  most common supported customizations that can be made to a Pelorus deployment.

## Configure Prometheus Retention

For detailed information about planning Prometheus storage capacity and configuration options please refer to the [operational aspects](https://prometheus.io/docs/prometheus/latest/storage/#operational-aspects) of the Prometheus documentation.

Prometheus is removing data older than 1 year, so if the metric you are interested in happened to be older than 1 year it won't be visible. This is configurable in the `values.yaml` file with the following option:
```yaml
prometheus_retention: 1y
```

Additionally, users have the option to configure maximum size of storage to be used by Prometheus. The oldest data will be removed first if it exceeds that limit. If the data is within retention time, but over retention size, it will also be removed.
```yaml
prometheus_retention_size: 1GB
```

## Configure Prometheus Persistent Volume (Recommended)

Unlike ephemeral volume that have a lifetime of a pod, persistent volume allows to withstand container restarts or crashes making Prometheus data resilient to such situations. Pelorus chart allows to use underlying [Prometheus Operator Storage](https://github.com/prometheus-operator/prometheus-operator/blob/main/Documentation/user-guides/storage.md#storage-provisioning-on-aws) capabilities by using Kubernetes [`StorageClass`](https://kubernetes.io/docs/concepts/storage/storage-classes/).

It is recommended to use Prometheus Persistent Volume together with the [Long Term Storage](#configure-long-term-storage-recommended).

To install or upgrade helm chart with PVC that uses default StorageClass and default 2Gi (can units be standardized?) capacity, use one additional field in the `values.yaml` file
```yaml
prometheus_storage: true
# prometheus_storage_pvc_capacity: "<PVC requested volume capacity>" # Optional, default 2Gi
# prometheus_storage_pvc_storageclass: "<your storage class name>"   # Optional, default "gp2"
```

Then run `helm upgrade` with updated `values.yaml` configuration
```shell
helm upgrade pelorus charts/pelorus --namespace pelorus --values values.yaml
```

To ensure PVC were properly created and Bound to the PV, run
```shell
oc get pvc --namespace pelorus
```

## Configure Long Term Storage (Recommended)

The Pelorus chart supports deploying a thanos (what is this?) instance for long term storage. It can use any S3 bucket provider. The following is an example of configuring a `values.yaml` file for [NooBaa](https://www.noobaa.io/) with the local s3 service name.
```yaml
bucket_access_point: s3.pelorus.svc:443
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
```

The default bucket name is thanos. It can be overridden by specifying the following field.
```yaml
thanos_bucket_name: <bucket name here>
```

Then run `helm upgrade` with updated `values.yaml` configuration:
```
helm upgrade pelorus charts/pelorus --namespace pelorus --values values.yaml
```

If you don't have an object storage provider, we recommend NooBaa as a free, open source option. You can follow our [NooBaa quickstart](Noobaa.md) to host an instance on OpenShift and configure Pelorus to use it.

## Deploying Across Multiple Clusters

By default, Pelorus will pull in data from the cluster in which it is running, but it also supports collecting data across multiple OpenShift clusters. In order to do this, the thanos sidecar can be configured to read from a shared S3 bucket across clusters. See [Pelorus Multi-Cluster Architecture](Architecture.md) for details. You define exporters for the desired metrics in each of the clusters and the main cluster's Grafana dashboard will display a combined view of the metrics collected in the shared S3 bucket via thanos.

## Configure Production Cluster

A production configuration example of `values.yaml` with one deploytime exporter, which uses AWS S3 bucket and AWS volume for Prometheus and tracks deployments to production.
```yaml
thanos_bucket_name: <bucket name here>
bucket_access_point: s3.us-east-2.amazonaws.com
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>

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
