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
| `exporters` | no | Specified which exporters to install. See [Configuring Exporters](#configuring-exporters). | Installs deploytime exporter only. |

## Configuring Exporters

An _exporter_ is a data collection application that pulls data from various tools and platforms and exposes it such that it can be consumed by Pelorus dashboards. Each exporter gets deployed individually alongside the core Pelorus stack.

Exporters can be deployed and configured via a list of `exporters.instances` inside the `values.yaml` file. Some exporters also require secrets to be created when integrating with external tools and platforms. A sample exporter configuration may look like this:


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

Additionally, you may want to deploy a single exporter multiple times to gather data from different sources. For example, if you wanted to pull commit data from both GitHub and a private GitHub Enterprise instance, you would deploy two instances of the Commit Time Exporter like so:

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

Each exporter additionally takes a unique set of environment variables to further configure its integrations and behavior. These can be set with literal keys names and values under `extraEnv` or by creating a kubernetes secret and listing the secret name under `env_from_secrets`. As detailed below.

### Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

We require that all builds associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label.

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
| PROVIDER | yes | Metric import provider | unset |
| `GIT_API` | no | Github API FQDN.  This allows the override for Github Enterprise users.  Currently only applicable to `github` provider type. | `api.github.com` |
| `GIT_PROVIDER` | no | Set Git provider type. Can be `github`, `gitlab`, or `bitbucket` | `github` |
| `LOG_LEVEL` | no | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `APP_LABEL` | no | Changes the label key used to identify applications  | `app.kubernetes.io/name`  |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
| DEPRECATED `GITHUB_USER` | no | User's github username | unset |
| DEPRECATED `GITHUB_TOKEN` | no | User's Github API Token | unset |
| DEPRECATED `GITHUB_API` | no | Github API FQDN.  This allows the override for Github Enterprise users. | `api.github.com` |

#### Webhook exporter (Commit Time)

**To enable, set the PROVIDER environment variable to "webhook".**

The Webhook exporter is responsible for collecting the following metric from an associated webhook/mongodb instance:

```
commit_timestamp{app, commit_hash, image_sha} timestamp
```

Deploy an instance of a webhook/mongodb and post build information to the webhook as part of your build. From there, the generic exporter will retrieve the build information from the db and query the respective git provider to get the commit time associated with the build.

Expected data model of build info sent to webhook/mongodb:
```
{"app": "APP NAME",
"commit":"COMMIT HASH",
"image_sha":"IMAGE HASH",
"git_provider": "PROVIDER", (i.e. github, gitlab, bitbucket)
"repo":"REPO URL",
"branch":"REPO BRANCH"}
```

Be sure to provide the secret associated with the deployed webhook/mongodb instance so that the exporter can connect to mongodb. You will also need to provide a github secret that allows the exporter to reach out to the appropriate git provider.

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

#### Suggested Secrets

Create a secret containing your Jira information.

    oc create secret generic jira-secret \
    --from-literal=SERVER=<Jira Server> \
    --from-literal=USER=<username> \
    --from-literal=TOKEN=<personal access token> \
    -n pelorus

For ServiceNow create a secret containing your ServiceNow information.

    oc create secret generic snow-secret \
    --from-literal=SERVER=<ServiceNow Server> \
    --from-literal=USER=<username> \
    --from-literal=TOKEN=<personal access token> \
    --from-literal=TRACKER_PROVICER=servicenow \
    --from-literal=APP_FIELD=<Custom app label field> \
    -n pelorus

#### Environment Variables

This exporter provides several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `PROVIDER` | no | Set the type of failure provider. One of `jira`, `servicenow` | `jira` |
| `LOG_LEVEL` | no | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `SERVER` | yes | URL to the Jira or ServiceNowServer  | unset  |
| `USER` | yes | Tracker Username | unset |
| `TOKEN` | yes | User's API Token | unset |
| `APP_FIELD` | no | Required for ServiceNow, field used for the Application label. ex: "u_appName" | 'u_application' |

### ServiceNow exporter details

The integration with ServiceNow is configured to process Incident objects that have been resolved (stage=6).  Since there are not Tags in all versions of ServiceNow there may be a need to configure a custom field on the Incident object to provide an application name to match Openshift Labels.  The exporter uses the opened_at field for created timestamp and the resolved_at field for the resolution timestamp.  The exporter will traverse through all the incidents and when a resolved_at field is populated it will create a resolution record.

A custom field can be configure with the following steps:

- Navigate to an existing Incident
- Use the upper left Menu and select Configure -> Form Layout
- Create a new field (String, Table or reference a List)
- You can use the API Explorer to verify the name of the field to be used as the APP_FIELD
