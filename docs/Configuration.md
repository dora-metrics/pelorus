# Configuration

## Configuring The Pelorus Stack

The Pelorus stack (Prometheus, Grafana, Thanos, etc.) can be configured by changing the `values.yaml` file that is passed to helm. The recommended practice is to make a copy of the one [provided in this repo](/charts/)deploy/values.yaml), and store in in your own configuration repo for safe keeping, and updating. Once established, you can make configuration changes by updating your `values.yaml` and applying the changes like so:

```
./runhelm.sh -v myclusterconfigs/pelorus/values.yaml
```

The following configurations may be made through the `values.yaml` file:

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `custom_ca` | no | Whether or not the cluster serves custom signed certificates for ingress (e.g. router certs). If `true` we will load the custom via the [certificate injection method](https://docs.openshift.com/container-platform/4.4/networking/configuring-a-custom-pki.html#certificate-injection-using-operators_configuring-a-custom-pki)  | `false`  |
| `extra_prometheus_hosts` | no | Configures additional prometheus instances for a multi-cluster setup. See [Deploying across multple clusters](/docs/Install.md#deploying-across-multiple-clusters) for details. | Nil |

## Configuring Exporters
    
### Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

In order for proper collection, we require that all builds associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label.

#### Deploying to OpenShift

Create a secret containing your GitHub token.

    oc create secret generic github-secret --from-literal=GITHUB_USER=<username> --from-literal=GITHUB_TOKEN=<personal access token> -n pelorus

Then deploy the chart.

    helm template charts/exporter/ -f exporters/committime/values.yaml --namespace pelorus | oc apply -f- -n pelorus

#### Configuration

This exporter supports several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `APP_LABEL` | no | Changes the label key used to identify applications  | `app.kubernetes.io/name`  |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
| `GITHUB_USER` | yes | User's github username | unset |
| `GITHUB_TOKEN` | yes | User's Github API Token | unset |


### Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happen in a production environment.

In order for proper collection, we require that all deployments associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label.

#### Deploying to OpenShift

Deploying to OpenShift is done via the exporter chart.

    helm template charts/exporter/ -f exporters/deploytime/values.yaml --namespace pelorus | oc apply -f- -n pelorus

#### Configuration

This exporter supports several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `APP_LABEL` | no | Changes the label key used to identify applications  | `app.kubernetes.io/name`  |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
    
### Failure Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a failure occurs in a production environment and when it is resolved.

#### Deploying to OpenShift

Create a secret containing your Jira information.

    oc create secret generic jira-secret \
    --from-literal=SERVER=<Jira Server> \
    --from-literal=USER=<username> \
    --from-literal=TOKEN=<personal access token> \
    --from-literal=PROJECT=<Jira Project> \
    -n pelorus


Deploying to OpenShift is done via the failure exporter Helm chart.

**_NOTE:_** Be sure to update the appropiate values if `values.yaml` if necessary.

    helm template charts/exporter/ -f exporters/failure/values.yaml --namespace pelorus | oc apply -f- -n pelorus

#### Configuration

This exporter supports several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `SERVER` | yes | URL to the Jira Server  | unset  |
| `PROJECT` | yes | Jira project to scan | unset |
| `USER` | yes | Jira Username | unset |
| `TOKEN` | yes | User's API Token | unset |
