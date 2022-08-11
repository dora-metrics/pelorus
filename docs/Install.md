
# Installation

The following will walk through the deployment of Pelorus.

**Prerequisites**
The following are required to deploy Pelorus:
* An OpenShift 4.7 or higher Environment
* A machine from which to run the install (usually your laptop)
  * The OpenShift Command Line Tool (oc)
  * [Helm3](https://github.com/helm/helm/releases)
  * jq
  * git

## Initial Deployment
Pelorus gets installed using three Helm charts. The first deploys the required Pelorus operators, the second deploys the core Pelorus stack, and the third deploys the exporters that gather the data.

The tool is installed into the `Pelorus` namespace by default.

**Procedure**
1. Clone the master repo or a different release.
```shell
git clone --depth 1 --branch v1.6.0 https://github.com/konveyor/pelorus
cd pelorus
oc create namespace pelorus
helm install operators charts/operators --namespace pelorus
```
1. Verify the operators are completely installed.
1. Install the Pelorus Helm chart.
```shell
helm install pelorus charts/pelorus --namespace pelorus
```
The following are deployed:

* Prometheus and Grafana operators
* The core Pelorus stack
    * A `Prometheus` instance
    * A `Grafana` instance
    * A `ServiceMonitor` instance for scraping the Pelorus exporters
    * A `GrafanaDatasource` pointing to Prometheus
    * A set of `GrafanaDashboards`. See [Dashboards](https://pelorus.readthedocs.io/en/latest/Dashboards/) for more details
* Deploy Time exporter

Additional configuration is required to deploy other exporters. See the [Configuration Guide](Configuration.md) for more information on exporters. Additional features can be enabled for the core stack.

## Customizing Pelorus
See [Configuring the Pelorus Stack](Configuration.md) for a complete list of possible configuration items. The following sections describe the most commonly supported Pelorus deployment customizations.

### Configure long term storage
The Pelorus chart supports deploying a Thanos instance for long term storage and can use any S3 bucket provider. The following is an example of configuring a values.yaml file for NooBaa with the local S3 service name.

> **Note:** This customization is recommended.

```
bucket_access_point: s3.noobaa.svc
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
```

The default bucket name is thanos but can be overriden by specifying an additional value for the bucket name.

```
bucket_access_point: s3.noobaa.svc
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
thanos_bucket_name: <bucket name here>
```

Then run `helm upgrade` with updated `values.yaml` configuration.

```
helm upgrade pelorus charts/deploy --namespace pelorus --values values.yaml
```
[NooBaa](https://www.noobaa.io/) is a recommended free, open source object storage provider. Follow the [NooBaa quickstart](Noobaa.md) to host an instance on OpenShift and configure it for Pelorus.

### Deploying Across Multiple Clusters

By default, this tool will pull in data from the cluster in which it is running. The tool also supports collecting data across mulitple OpenShift clusters. In order to do this, the Thanos sidecar can be configured to read from a shared S3 bucket across clusters. See [Pelorus Multi-Cluster Architecture](Architecture.md) for details.

Exporters for the desired metrics in each of the clusters which metrics will be evaluated must be defined. The main cluster's Grafana dashboard will display a combined view of the metrics collected in the shared S3 bucket via Thanos.

## Configuring the production cluster
The production configuration example with one Deploy Time Exporter uses the same AWS S3 bucket and tracks deployments to production.
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
## Uninstalling Pelorus
Removing Pelorus is performed using these two commands.
```
    helm uninstall pelorus --namespace pelorus
    helm uninstall operators --namespace pelorus
```
