# Configuration

## Configuring The Pelorus Stack

The Pelorus stack (Prometheus, Grafana, Thanos, etc.) can be configured by changing the `values.yaml` file that is passed to helm. The recommended practice is to make a copy of the one [provided in this repo](https://github.com/redhat-cop/pelorus/blob/v1.2.1-rc/charts/pelorus/values.yaml), and store in in your own configuration repo for safe keeping, and updating. Once established, you can make configuration changes by updating your `values.yaml` and applying the changes like so:

```
helm upgrade pelorus charts/pelorus --namespace pelorus --values myclusterconfigs/pelorus/values.yaml
```

The following configurations may be made through the `values.yaml` file:

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `openshift_prometheus_htpasswd_auth` | yes | The contents for the htpasswd file that Prometheus will use for basic authentication user. | User: `internal`, Password: `changeme` |
| `openshift_prometheus_basic_auth_pass` | yes | The password that grafana will use for its Prometheus datasource. Must match the above. | `changme` |
| `custom_ca` | no | Whether or not the cluster serves custom signed certificates for ingress (e.g. router certs). If `true` we will load the custom via the [certificate injection method](https://docs.openshift.com/container-platform/4.4/networking/configuring-a-custom-pki.html#certificate-injection-using-operators_configuring-a-custom-pki)  | `false`  |
| `extra_prometheus_hosts` | no | Configures additional prometheus instances for a multi-cluster setup. See [Deploying across multple clusters](/page/Install.md#deploying-across-multiple-clusters) for details. | Nil |
| `exporters` | no | Specified which exporters to install. See [Configuring Exporters](#configuring-exporters). | Installs deploytime exporter only. |

## Configuring Exporters

An _exporter_ is a data collection application that pulls data from various tools and platforms and exposes it such that it can be consumed by Pelorus dashboards. Each exporter gets deployed individually alongside the core Pelorus stack.

Exporters can be deployed and configured via the `exporters.instances` list of a `values.yaml` file. Some exporters also require secrets to be created when integrating with external tools and platforms. A sample exporter configuration may look like this:

```
exporters:
  instances:
    # Values file for exporter helm chart
  - app_name: deploytime-exporter
    source_context_dir: exporters/
    extraEnv:
    - name: APP_FILE
      value: deploytime/app.py
    source_ref: master
    source_url: https://github.com/redhat-cop/pelorus.git
```

Deploying additional exporters can be done by adding to the `exporters.instances` list. In some cases, you may want to deploy a single exporter multiple times to gather data from different sources. For example, if you wanted to pull commit data from both GitHub and a private GitHub Enterprise instance, you would deploy two instances of the Commit Time Exporter like so:

```
exporters:
  instances:
  - app_name: committime-github
    env_from_secrets: 
    - github-credentials
    source_context_dir: exporters/
    extraEnv:
    - name: APP_FILE
      value: committime/app.py
    source_ref: master
    source_url: https://github.com/redhat-cop/pelorus.git
  - app_name: committime-gh-enterprise
    env_from_secrets: 
    - github-enterprise-credentials
    source_context_dir: exporters/
    extraEnv:
    - name: APP_FILE
      value: committime/app.py
    source_ref: master
    source_url: https://github.com/redhat-cop/pelorus.git
```

Each exporter additionally takes a unique set of environment variables to further configure its integrations and behavior. Each of those environment variables can be set either by placing the literal keys and values under `extraEnv` or by creating a kubernetes secre with literal values and listing the secret name under `env_from_secrets`. Those configurations are detailed below.

### Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

In order for proper collection, we require that all builds associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label. 

Currently we support GitHub and GitLab, with BitBucket coming soon. Open an issue or a pull request to add support for additional Git providers!

#### Suggested Secrets

Create a secret containing your Git username and token.

    oc create secret generic github-secret --from-literal=GIT_USER=<username> --from-literal=GIT_TOKEN=<personal access token> -n pelorus

Create a secret containing your Git username, token, and API.  An API example is `github.mycompany.com/api/v3`

    oc create secret generic github-secret --from-literal=GIT_USER=<username> --from-literal=GIT_TOKEN=<personal access token> --from-literal=GIT_API=<api> -n pelorus

#### Sample Values

```
exporters:
  instances:
  - app_name: committime-exporter
    env_from_secrets: 
    - github-secret
    source_context_dir: exporters/
    extraEnv:
    - name: APP_FILE
    value: committime/app.py
    source_ref: master
    source_url: https://github.com/redhat-cop/pelorus.git
```

#### Environment Variables

This exporter provides several configuration options, passed via environment variables.


| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `GIT_USER` | yes | User's github username | unset |
| `GIT_TOKEN` | yes | User's Github API Token | unset |
| `GIT_API` | no | Github API FQDN.  This allows the override for Github Enterprise users.  Currently only applicable to `github` provider type. | `api.github.com` |
| `GIT_PROVIDER` | no | Set Git provider type. Can be `github`, `gitlab`, or `bitbucket` | `github` |
| `LOG_LEVEL` | no | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `APP_LABEL` | no | Changes the label key used to identify applications  | `app.kubernetes.io/name`  |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
| DEPRECATED `GITHUB_USER` | no | User's github username | unset |
| DEPRECATED `GITHUB_TOKEN` | no | User's Github API Token | unset |
| DEPRECATED `GITHUB_API` | no | Github API FQDN.  This allows the override for Github Enterprise users. | `api.github.com` |



### Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happen in a production environment.

In order for proper collection, we require that all deployments associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label.

#### Environment Variables

This exporter provides several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `LOG_LEVEL` | no | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `APP_LABEL` | no | Changes the label key used to identify applications  | `app.kubernetes.io/name`  |
| `PROD_LABEL` | no | Changes the label key used to identify namespaces that are considered production environments. | unset; matches all namespaces |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
    
### Failure Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a failure occurs in a production environment and when it is resolved.

#### Suggeste Secrets

Create a secret containing your Jira information.

    oc create secret generic jira-secret \
    --from-literal=SERVER=<Jira Server> \
    --from-literal=USER=<username> \
    --from-literal=TOKEN=<personal access token> \
    --from-literal=PROJECT=<Jira Project> \
    -n pelorus

#### Environment Variables

This exporter provides several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `LOG_LEVEL` | no | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `SERVER` | yes | URL to the Jira Server  | unset  |
| `PROJECT` | yes | Jira project to scan | unset |
| `USER` | yes | Jira Username | unset |
| `TOKEN` | yes | User's API Token | unset |
