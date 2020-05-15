
# Installation

The following will walk through the deployment of Pelorus.

### Prerequisites

Before deploying the tooling, you must have the following prepared

* An OpenShift 3.11 or higher Environment
* A machine from which to run the install (usually your laptop)
  * The OpenShift Command Line Tool (oc)
  * [Helm3](https://github.com/helm/helm/releases)
  * jq

### Deploy Long Term Storage

#### Configure Storage Security

To allow minio to run, add a security constraint context. Run the following command from within the root repository directory

```
oc apply -f storage/minio-scc.yaml
```

#### Deploy Object Storage for Pelorus

To retain Pelorus dashboard data in the long-term, we'll deploy an instance of [minio](https://github.com/helm/charts/tree/master/stable/minio) and create a bucket called `thanos`.

```
helm install --set "buckets[0].name=thanos" \
--set "buckets[0].policy=none" \
--set "buckets[0].purge=false" \
--set "configPathmc=/tmp/minio/mc" \
--set "DeploymentUpdate.type=\"Recreate\"" pelorus-minio stable/minio
```

* Recreate mode is used. RollingDeployments won't allow re-deployment while a pvc is in use
* Configuration and certificate path changed to [work with openshift]([https://github.com/minio/mc/issues/2640](https://github.com/minio/mc/issues/2640))

#### Secure Minio Object Storage

Secure minio using a [service serving certificate](https://docs.openshift.com/container-platform/4.1/authentication/certificates/service-serving-certificate.html)

```
helm upgrade --set "certsPath=/tmp/minio/certs" \
--set "tls.enabled=true" \
--set "tls.certSecret=pelorus-minio-tls" \
--set "tls.privateKey=tls.key,tls.publicCrt=tls.crt" \
--set "service.annotations.service\.beta\.openshift\.io/serving-cert-secret-name=pelorus-minio-tls" \
--set "DeploymentUpdate.type=\"Recreate\"" pelorus-minio stable/minio
```
Other storage configuration can be found [here](/docs/Storage.md).

### Deploy Pelorus

To deploy Pelorus, run the following script from within the root repository directory

```
./runhelm.sh -s "bucket_access_point=pelorus-minio.<my-namespace>.svc:9000" \
-s "bucket_access_key=AKIAIOSFODNN7EXAMPLE" \
-s "bucket_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

By default, Pelorus will be installed in a namespace called `pelorus`. You can customize this by passing `-n <my-namespace>` like so:

```
./runhelm.sh -n <my-namespace> \
-s "bucket_access_point=pelorus-minio.<my-namespace>.svc:9000" \
-s "bucket_access_key=AKIAIOSFODNN7EXAMPLE" \
-s "bucket_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

Pelorus also has additional (optional) exporters that can be deployed to gather additional data and integrate with external systems. Consult the docs for each exporter below:

* [Commit Time Exporter](/docs/Configuration.md#commit-time-exporter)
* [Deploy Time](/docs/Configuration.md#deploy-time-exporter)

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
./runhelm.sh -v extra-prometheus-hosts.yaml
```

### Cleaning Up

Cleaning up Pelorus is very simple.

    helm template --namespace pelorus pelorus ./charts/deploy/ | oc delete -f- -n pelorus

