# Configuration

The Pelorus Core configuration applies to Prometheus, Grafana, Thanos and other operational aspects of the Pelorus stack.

Those configuration options are used in the Pelorus configuration object YAML file to create Pelorus application instance.

Each Pelorus Core configuration option must be placed under `spec` in the Pelorus configuration object YAML file as in the example:

```yaml
kind: Pelorus
apiVersion: charts.pelorus.dora-metrics.io/v1alpha1
metadata:
  name: pelorus-pelorus-instance
  namespace: pelorus
spec:
  exporters:
    [...] # Pelorus exporters configuration options
  # Pelorus Core configuration options
```

For configuration options for exporters, check [its configuration guide](PelorusExporters.md).

## Example

Configuration part of the Pelorus object YAML file, with some non-default options:

```yaml
kind: Pelorus
apiVersion: charts.pelorus.dora-metrics.io/v1alpha1
metadata:
  name: pelorus-instance
  namespace: pelorus
spec:
  exporters:
    [...] # Pelorus exporters configuration options
  openshift_prometheus_basic_auth_pass: mysecretpassword
  openshift_prometheus_htpasswd_auth: 'internal:{SHA}CM2SM2eJAAllfquBJ1M3m9syHus='
  prometheus_retention: 500d
  prometheus_retention_size: 2GB
  prometheus_storage: true
  prometheus_storage_pvc_capacity: 3Gi
  prometheus_storage_pvc_storageclass: mystorageclass
```

## List of all configuration options

| Variable | Required | Default Value |
|----------|----------|---------------|
| [[exporters]](PelorusExporters.md) | yes | - |
| [prometheus_retention_size](#prometheus_retention_size) | no | `1GB` |
| [prometheus_retention](#prometheus_retention) | no | `1y` |
| [prometheus_storage](#prometheus_storage) | no | `false` |
| [prometheus_storage_pvc_capacity](#prometheus_storage_pvc_capacity) | no | `2Gi` |
| [prometheus_storage_pvc_storageclass](#prometheus_storage_pvc_storageclass) | no | `gp2` |
| [openshift_prometheus_htpasswd_auth](#openshift_prometheus_htpasswd_auth)  | no | `internal:{SHA}+pvrmeQCmtWmYVOZ57uuITVghrM=` |
| [openshift_prometheus_basic_auth_pass](#openshift_prometheus_basic_auth_pass) | no | `changeme` |
| [[federate_openshift_monitoring]](#federate_openshift_monitoring) | no | - |
| [[federated_prometheus_hosts]](#federated_prometheus_hosts) | no | - |
| [[external_prometheus_hosts]](#external_prometheus_hosts) | no | - |
| [thanos_version](#thanos_version) | no | `v0.28.0` |
| [bucket_access_point](#bucket_access_point) | no | - |
| [bucket_access_key](#bucket_access_key) | no | - |
| [bucket_secret_access_key](#bucket_secret_access_key) | no | - |
| [thanos_bucket_name](#thanos_bucket_name) | no | `thanos` |
| [custom_ca](#custom_ca) | no  | - |

## Prometheus

Pelorus allows to configure few aspects of [Prometheus](https://prometheus.io/), that is deployed as an [Prometheus Operator](https://prometheus-operator.dev/) available from the [OLM dependency](https://olm.operatorframework.io/docs/concepts/olm-architecture/dependency-resolution/) mechanism.

For detailed information about planning Prometheus storage capacity and configuration options please refer to the [operational aspects](https://prometheus.io/docs/prometheus/latest/storage/#operational-aspects) of the Prometheus documentation.

### Prometheus Data Retention

###### prometheus_retention_size

- **Required:** no
    - **Default Value:** 1GB
- **Type:** string

: Users have the option to configure maximum size of storage to be used by Prometheus. The oldest data will be removed first if it exceeds that limit. Even if the data is within retention time, but over retention size, it will also be removed.

: Units supported: MB, GB, TB, PB, EB

###### prometheus_retention

- **Required:** no
    - **Default Value:** 1y
- **Type:** string

: Prometheus is removing data older than 1 year, so if the metric you are interested in happened to be older than 1 year it won't be visible.

: Units supported: d, y


### Prometheus Persistent Volume

Unlike ephemeral volume that have a lifetime of a pod, persistent volume allows to withstand container restarts or crashes making Prometheus data resilient to such situations. Pelorus allows to use underlying [Prometheus Operator Storage](https://prometheus-operator.dev/docs/operator/storage/#storage-provisioning-on-aws) capabilities by using Kubernetes [`StorageClass`](https://kubernetes.io/docs/concepts/storage/storage-classes/).

It is recommended to use Prometheus Persistent Volume **together** with [Thanos](#thanos) for the long term storage.

###### prometheus_storage

- **Required:** no
    - **Default Value:** false
- **Type:** boolean

: Controls wether Prometheus should use persistent volume. If set to `true` [PersistentVolumeClaim](https://docs.openshift.com/container-platform/4.11/storage/understanding-persistent-storage.html#persistent-volume-claims_understanding-persistent-storage) will be created.

###### prometheus_storage_pvc_capacity

- **Required:** no
    - **Default Value:** 2Gi
- **Type:** string

: The amount of storage available to the PVC.

: Units supported: As documented in the [Quantity](https://kubernetes.io/docs/reference/kubernetes-api/common-definitions/quantity/) Kubernetes API

###### prometheus_storage_pvc_storageclass

- **Required:** no
    - **Default Value:** gp2
- **Type:** string

: [StorageClass Name](https://docs.openshift.com/container-platform/4.11/storage/understanding-persistent-storage.html#persistent-volume-claims_understanding-persistent-storage) to be used for the [PersistentVolumeClaim](https://docs.openshift.com/container-platform/4.11/storage/understanding-persistent-storage.html#persistent-volume-claims_understanding-persistent-storage).

### Prometheus credentials

###### openshift_prometheus_htpasswd_auth

- **Required:** no
    - **Default Value:** internal:{SHA}+pvrmeQCmtWmYVOZ57uuITVghrM=
- **Type:** string

: Credentials for the `internal` user that are used by Grafana to communicate with the Prometheus instance deployed by Pelorus. Those credentials must use `internal` user name and must match the [openshift_prometheus_basic_auth_pass](#openshift_prometheus_basic_auth_pass) password from the [Grafana credentials](#grafana-credentials) configuration option.

: Format supported: Base64-encoded SHA-1

: **Note:** The generate new password for the `internal` user, you may invoke the `htpasswd` CLI as in the example:
```shell
$ htpasswd -nbs internal <my-secret-password>
```

### Multiple Prometheus

By default, Pelorus gathers the data from the Prometheus instance deployed in the same cluster in which it is running. To collect data across multiple OpenShift clusters, additional Prometheus scrape hosts have to be configured. To do this `federated_prometheus_hosts` and `external_prometheus_hosts` configuration options are used.

###### federate_openshift_monitoring

**Required:** no
**Type:** object

When configured, Pelorus can automatically integrate into OpenShift's Prometheus-based monitoring stack to pull in data about pods, namespaces, and such to be used in custom dashboards. The properties of this object include:

: * enabled - a boolean that determines whether or not to enable this feature. default is `false`.
: * metrics_filter - a block of freeform yaml that can be used to determine which metrics to pull in from openshift-monitoring. Default value is:

    ```yaml
    # Pull in all openshift and kubernetes metrics
    - '{job="kube-state-metrics"}'
    - '{job="openshift-state-metrics"}'
    ```

Examples




###### federated_prometheus_hosts

- **Required:** no
- **Type:** list

It is a list that consists of three configuration items per additional [Federation](https://prometheus.io/docs/prometheus/latest/federation/) host:
: * id - a description of the prometheus host (this will be used as a label to select metrics in the federated instance).
: * hostname - the fully qualified domain name or ip address of the host with the extra Prometheus instance
: * password - the password used for the `internal` basic auth account (this is provided by the k8s metrics prometheus instances in a secret).

Prometheus will scrape data from `/federate` endpoint.

: Example:
```yaml
federated_prometheus_hosts:
- id: "ci-1"
  hostname: "prometheus-k8s-openshift-monitoring.apps.ci-1.example.com"
  password: "<redacted>"

- id: "ci-2"
  hostname: "prometheus-k8s-openshift-monitoring.apps.ci-2.example.com"
  password: "<redacted>"
```

###### external_prometheus_hosts

- **Required:** no
- **Type:** list

It is a list that consists of three configuration items per additional scrape host:
: * id - a description of the scrape host
: * hostname - the fully qualified domain name or ip address of the host

Prometheus will scrape data from `/metrics` endpoint.

: Example:
```yaml
external_prometheus_hosts:
- id: "prometheus-node"
  hostname: "node.demo.do.prometheus.io"

- id: "webhook"
  hostname: "webhook.example.com"
```

## Grafana

Grafana is a dashboard which represents data stored in the [Prometheus](#prometheus). Is deployed as an Grafana Operator available from the OLM dependency mechanism.

### Grafana credentials

###### openshift_prometheus_basic_auth_pass

- **Required:** no
    - **Default Value:** changeme
- **Type:** string

: The password that grafana will use for its Prometheus datasource. Must match the [openshift_prometheus_htpasswd_auth](#openshift_prometheus_htpasswd_auth).

## Thanos

The Pelorus chart supports deploying a [Thanos](https://thanos.io/) instance for long term storage. If you don't have an object storage provider, we recommend NooBaa as a free, open source option. You can check [NooBaa for Long Term Storage](Noobaa.md) to guide on how to host an instance on OpenShift and configure Pelorus to use it.

###### thanos_version

- **Required:** no
    - **Default Value:** v0.28.0
- **Type:** string

: Which Thanos version from the [Official Thanos podman image](https://quay.io/repository/thanos/thanos) use.

###### bucket_access_point

- **Required:** no
- **Type:** string

: S3 named network endpoint that is used to perform S3 object operations

###### bucket_access_key

- **Required:** no
- **Type:** string

: S3 Access Key ID

###### bucket_secret_access_key

- **Required:** no
- **Type:** string

: S3 Secret Access Key

###### thanos_bucket_name

- **Required:** no
    - **Default Value:** thanos
- **Type:** string

: S3 bucket name

## Custom PKI

###### custom_ca

- **Required:** no
    - **Default Value:** false
- **Type:** boolean

: Whether or not the cluster serves custom signed certificates for ingress (e.g. router certs). If `true`, we will load the custom via the [certificate injection method](https://docs.openshift.com/container-platform/4.11/networking/configuring-a-custom-pki.html#certificate-injection-using-operators_configuring-a-custom-pki).

## Deploying Across Multiple Clusters

By default, Pelorus will pull in data from the cluster in which it is running, but it also supports collecting data across multiple OpenShift clusters. In order to do this, the thanos sidecar can be configured to read from a shared S3 bucket across clusters. See [Pelorus Multi-Cluster Architecture](../../Architecture.md#multi-cluster-architecture-production) for details. You define exporters for the desired metrics in each of the clusters and the main cluster's Grafana dashboard will display a combined view of the metrics collected in the shared S3 bucket via thanos.