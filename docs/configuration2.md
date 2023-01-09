# Customizing Pelorus

See [Configuring the Pelorus Stack](Configuration.md) for a full readout of all possible configuration items. The following sections describe the  most common supported customizations that can be made to the Pelorus configuration object YAML file.

## Configure Prometheus Retention

For detailed information about planning Prometheus storage capacity and configuration options please refer to the [operational aspects](https://prometheus.io/docs/prometheus/latest/storage/#operational-aspects) of the Prometheus documentation.

Prometheus is removing data older than 1 year, so if the metric you are interested in happened to be older than 1 year it won't be visible. This is configurable in the Pelorus configuration object YAML file with the following option:
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

To install Pelorus with PVC that uses default `gp2` StorageClass and default `2Gi` capacity, ensure `prometheus_storage` is set to `true` in the Pelorus configuration object YAML file:
```yaml
prometheus_storage: true
# prometheus_storage_pvc_capacity: "<PVC requested volume capacity>" # Optional, default 2Gi
# prometheus_storage_pvc_storageclass: "<your storage class name>"   # Optional, default "gp2"
```

To ensure PVC were properly created and Bound to the PV, run after Pelorus instance creation:
```shell
$ oc get pvc --namespace pelorus
NAME                                                               STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
prometheus-prometheus-pelorus-db-prometheus-prometheus-pelorus-0   Bound    pvc-fe8ac17c-bd23-47da-9c72-057349a59209   2Gi        RWO            gp2            10s
prometheus-prometheus-pelorus-db-prometheus-prometheus-pelorus-1   Bound    pvc-3f815e71-1121-4f39-8174-0243071f281c   2Gi        RWO            gp2            10s

```

## Configure Long Term Storage (Recommended)

The Pelorus chart supports deploying a [Thanos](https://thanos.io/) instance for long term storage. It can use any S3 bucket provider. The following is an example of configuring a `pelorus-sample-instance.yaml` file for [NooBaa](https://www.noobaa.io/) with the local s3 service name.
```yaml
bucket_access_point: s3.pelorus.svc:443
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
```

The default bucket name is thanos. It can be overridden by specifying the following field.
```yaml
thanos_bucket_name: <bucket name here>
```

Then deploy Pelorus as described in the [Installation](Install.md) doc.

If you don't have an object storage provider, we recommend NooBaa as a free, open source option. You can follow our [NooBaa quickstart](Noobaa.md) to host an instance on OpenShift and configure Pelorus to use it.

## Deploying Across Multiple Clusters

By default, Pelorus will pull in data from the cluster in which it is running, but it also supports collecting data across multiple OpenShift clusters. In order to do this, the thanos sidecar can be configured to read from a shared S3 bucket across clusters. See [Pelorus Multi-Cluster Architecture](Architecture.md) for details. You define exporters for the desired metrics in each of the clusters and the main cluster's Grafana dashboard will display a combined view of the metrics collected in the shared S3 bucket via thanos.

## Configure Production Cluster

A production configuration example of the Pelorus configuration object YAML file `pelorus-sample-instance.yaml`:
```yaml
kind: Pelorus
apiVersion: charts.pelorus.konveyor.io/v1alpha1
metadata:
  name: pelorus-production
  namespace: pelorus
spec:
  exporters:
    global: {}
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
      - app_name: failuretime-exporter
        exporter_type: failure
      - app_name: committime-exporter
        exporter_type: committime
  extra_prometheus_hosts: null
  openshift_prometheus_basic_auth_pass: changeme
  openshift_prometheus_htpasswd_auth: 'internal:{SHA}+pvrmeQCmtWmYVOZ57uuITVghrM='
  prometheus_retention: 1y
  prometheus_retention_size: 1GB
  prometheus_storage: true
  prometheus_storage_pvc_capacity: 20Gi
  prometheus_storage_pvc_storageclass: gp2
  thanos_bucket_name: <bucket name here>
  bucket_access_point: s3.us-east-2.amazonaws.com
  bucket_access_key: <your access key>
  bucket_secret_access_key: <your secret access key>
```