# Customizing Pelorus

There are two main configuration parts required by Pelorus to serve it's function:

- [Pelorus Core Configuration](./PelorusCore.md)
- [Pelorus Exporters Configuration](./PelorusExporters.md)

This part of the documentation will focus on the recommended production settings for the [Pelorus Core Configuration](./PelorusCore.md).

## Pelorus Core Production Cluster Configuration

### Internal user password

There are two configuration options that are needed to be adjusted for the `internal` user's credentials:

- [openshift_prometheus_htpasswd_auth](./PelorusCore.md#prometheus-credentials)
- [openshift_prometheus_basic_auth_pass](./PelorusCore.md#grafana-credentials)

### Configure Prometheus Retention and PV

Prometheus is removing data older than 1 year and if within that time the default maximum storage of 1GB is used the data will get removed as well.
There are two configuration options that allows to modify those retention values:

- [prometheus_retention](./PelorusCore.md#prometheus_retention)
- [prometheus_retention_size](./PelorusCore.md#prometheus_retention_size)

Additionaly it is recommended to create Persistent Volumes to withstand prometheus container restarts. To enable that the [prometheus_storage](./PelorusCore.md#prometheus_storage) needs to be set to `true` and additionally PVC configuration options controls how it should be created. Relevant options are:

- [prometheus_storage](./PelorusCore.md#prometheus_storage)
- [prometheus_storage_pvc_capacity](./PelorusCore.md#prometheus_storage_pvc_capacity)
- [prometheus_storage_pvc_storageclass](./PelorusCore.md#prometheus_storage_pvc_storageclass)

### Configure Long Term Storage

The [Configure Prometheus Retention and PV](#configure-prometheus-retention-and-pv) allows to withstand prometheus container restarts, however to ensure data is preserved we recommend deploying Prometheus with the [Thanos](./PelorusCore.md#thanos).

There are four configuration options to enable [Thanos](./PelorusCore.md#thanos):

- [thanos_bucket_name](./PelorusCore.md#thanos_bucket_name)
- [bucket_access_point](./PelorusCore.md#bucket_access_point)
- [bucket_access_key](./PelorusCore.md#bucket_secret_access_key)
- [bucket_secret_access_key](./PelorusCore.md#bucket_secret_access_key)

> **Note:** If you don't have an object storage provider, we recommend NooBaa as a free, open source option. You can follow our [NooBaa quickstart](./Noobaa.md) to host an instance on OpenShift and configure Pelorus to use it.

### Example

A production configuration example of the Pelorus configuration object YAML:

```yaml
kind: Pelorus
apiVersion: charts.pelorus.konveyor.io/v1alpha1
metadata:
  name: pelorus-production
  namespace: pelorus
spec:
  exporters:
    [...] # Pelorus exporters configuration options

  # Internal user password
  openshift_prometheus_basic_auth_pass: mysecretpassword
  openshift_prometheus_htpasswd_auth: 'internal:{SHA}CM2SM2eJAAllfquBJ1M3m9syHus='

  # Configure Prometheus Retention and PV
  prometheus_retention: 1y
  prometheus_retention_size: 2GB
  prometheus_storage: true
  prometheus_storage_pvc_capacity: 20Gi
  prometheus_storage_pvc_storageclass: gp2

  # Configure Long Term Storage
  thanos_bucket_name: <bucket name here>
  bucket_access_point: <s3 access point here>
  bucket_access_key: <your access key>
  bucket_secret_access_key: <your secret access key>
```

## Deploying Across Multiple Clusters

Please refer to the [Deploying Across Multiple Clusters](./PelorusCore.md#deploying-across-multiple-clusters) for information about using Pelorus across multiple clusters.