# Configuration

## Configuring The Pelorus Stack

The Pelorus stack (Prometheus, Grafana, Thanos, etc.) can be configured by changing the `values.yaml` file that is passed to helm. The recommended practice is to make a copy of the one [values.yaml](https://github.com/konveyor/pelorus/blob/master/charts/pelorus/values.yaml) file and [charts/pelorus/configmaps/](https://github.com/konveyor/pelorus/blob/master/charts/pelorus/configmaps) directory, and store in in your own configuration repo for safe keeping, and updating. Once established, you can make configuration changes by updating your `charts/pelorus/configmaps` files with `values.yaml` and applying the changes like so:

```
oc apply -f `myclusterconfigs/pelorus/configmaps
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

There are currently three _exporter_ types which needs to be specified via `exporters.instances.exporter_type` value, those are `deploytime`, `failure` or `comittime`.


Exporters can be deployed via a list of `exporters.instances` inside the `values.yaml` file that corresponds to the OpenShift ConfigMap configurations from the `charts/pelorus/configmaps/` directory. Some exporters also require secrets to be created when integrating with external tools and platforms. A sample exporter configuration may look like this:

```yaml
exporters:
  instances:
  - app_name: deploytime-exporter
    exporter_type: deploytime
    env_from_configmaps:
    - pelorus-config
    - deploytime-config
```

Additionally, you may want to deploy a single exporter multiple times to gather data from different sources. For example, if you wanted to pull commit data from both GitHub and a private GitHub Enterprise instance, you would deploy two instances of the Commit Time Exporter.

Each exporter additionally takes a unique set of environment variables to further configure its integrations and behavior. These can be set by using example ConfigMap object configurations similarly to the kubernetes secrets and listing them under `env_from_configmaps` or under `env_from_secrets` accordingly. As shown below.

```yaml
exporters:
  instances:
  - app_name: committime-github
    exporter_type: comittime
    env_from_secrets:
    - github-credentials
    env_from_configmaps:
    - pelorus-config
    - committime-config

  - app_name: committime-gh-enterprise
    exporter_type: comittime
    env_from_secrets:
    - github-enterprise-credentials
    env_from_configmaps:
    - pelorus-config
    - comittime-enterprise-config
```

### ConfigMap configuration values

Configuration for each exporter is done via ConfigMap objects. Best practice is to store the folder outside of local Pelorus Git repository and modify accordingly.
Each ConfigMap must be in a separate file and must be applied to the cluster before deploying pelorus helm chart.

ConfigMap can be applied individually or all together:
```shell
# Only deploytime ConfigMap
oc apply -f charts/pelorus/configmaps/deploytime.yaml

# All at once
oc apply -f charts/pelorus/configmaps/
```

Example ConfigMap for the `deploytime-exporter` with the unique name `deploytime-config`:
```
apiVersion: v1
kind: ConfigMap
metadata:
  name: deploytime-config
  namespace: pelorus
data:
  PROD_LABEL: "default"    # "" / PROD_LABEL is ignored if NAMESPACES are provided
  NAMESPACES: "default"    # ""
```

### Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

We require that all builds associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label.

Currently we support GitHub and GitLab, with BitBucket coming soon. Open an issue or a pull request to add support for additional Git providers!

#### Annotated Binary (local) source build support

Commit Time Exporter may be used in conjunction with Builds where values required to gather commit time from the source repository are missing. In such case each Build is required to be annotated with two values allowing Commit Time Exporter to calculate metric from the Build.

To annotate Build use the following commands:

```shell
oc annotate build <build-name> -n <namespace> --overwrite io.openshift.build.commit.id=<commit_hash>

oc annotate build <build-name> -n <namespace> --overwrite io.openshift.build.source-location=<repo_uri>
```

Custom Annotation names may also be configured using ConfigMap Data Values.

Note: The requirement to label the build with `app.kubernetes.io/name=<app_name>` for the annotated Builds applies.

#### Suggested Secrets

Create a secret containing your Git username and token.

```shell
oc create secret generic github-secret --from-literal=GIT_USER=<username> --from-literal=GIT_TOKEN=<personal access token> -n pelorus
```

Create a secret containing your Git username, token, and API.  An API example is `github.mycompany.com/api/v3`

```shell
oc create secret generic github-secret --from-literal=GIT_USER=<username> --from-literal=GIT_TOKEN=<personal access token> --from-literal=GIT_API=<api> -n pelorus
```

#### Instance Config

```yaml
exporters:
  instances:
  - app_name: committime-exporter
    exporter_type: committime
    env_from_secrets:
    - github-secret
    env_from_configmaps:
    - pelorus-config
    - committime-config
```

#### ConfigMap Data Values

This exporter provides several configuration options, passed via `pelorus-config` and `committime-config` variables. User may define own ConfigMaps and pass to the committime exporter in a similar way.

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `GIT_USER` | yes | User's github username | unset |
| `GIT_TOKEN` | yes | User's Github API Token | unset |
| `GIT_API` | no | Github API FQDN.  This allows the override for Github Enterprise users.  Currently only applicable to `github` provider type. | `api.github.com` |
| `GIT_PROVIDER` | no | Set Git provider type. Can be `github`, `gitlab`, or `bitbucket` | `github` |
| `LOG_LEVEL` | no | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `APP_LABEL` | no | Changes the label key used to identify applications  | `app.kubernetes.io/name`  |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
| `PELORUS_DEFAULT_KEYWORD` | no | ConfigMap default keyword. If specified it's used in other data values to indicate "Default Value" should be used | `default` |
| `COMMIT_HASH_ANNOTATION` | no | Annotation name associated with the Build from which hash is used to calculate commit time | `io.openshift.build.commit.id` |
| `COMMIT_REPO_URL_ANNOTATION` | no | Annotation name associated with the Build from which GIT repository URL is used to calculate commit time | `io.openshift.build.source-location` |
  

### Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happen in a production environment.

In order for proper collection, we require that all deployments associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label.

#### Instance Config

```yaml
exporters:
  instances:
  - app_name: deploytime-exporter
    exporter_type: deploytime
    env_from_configmaps:
    - pelorus-config
    - deploytime-config
```

#### ConfigMap Data Values

This exporter provides several configuration options, passed via `pelorus-config` and `deploytime-config` variables. User may define own ConfigMaps and pass to the committime exporter in a similar way.

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `LOG_LEVEL` | no | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `APP_LABEL` | no | Changes the label key used to identify applications  | `app.kubernetes.io/name`  |
| `PROD_LABEL` | no | Changes the label key used to identify namespaces that are considered production environments. | unset; matches all namespaces |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
| `PELORUS_DEFAULT_KEYWORD` | no | ConfigMap default keyword. If specified it's used in other data values to indicate "Default Value" should be used | `default` |

### Failure Time Exporter

The job of the failure time exporter is to capture the timestamp at which a failure occurs in a production environment and when it is resolved.

Failure Time Exporter may be deployed with one of three backends, such as JIRA, GithHub Issues and ServiceNow. In one clusters' namespace there may be multiple instances of the Failure Time Exporter for each of the backends or/and watched projects.

Each of the backend requires specific [configuration](#failureconfigmap), that may be used via ConfigMap associated with the exporter instance.

For GitHub Issues and JIRA backends we require that all issues associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label, or custom label if it was configured via `APP_LABEL`.

#### Suggested Secrets

Create a secret containing your Jira information.

```shell
oc create secret generic jira-secret \
--from-literal=SERVER=<Jira Server> \
--from-literal=USER=<username/e-mail> \
--from-literal=TOKEN=<personal access token> \
-n pelorus
```

For Github create a secret containing your Github token.

```shell
oc create secret generic github-issue-secret \
--from-literal=TOKEN=<personal access token> \
-n pelorus
```

For ServiceNow create a secret containing your ServiceNow information.

```shell
oc create secret generic snow-secret \
--from-literal=SERVER=<ServiceNow Server> \
--from-literal=USER=<username> \
--from-literal=TOKEN=<personal access token> \
--from-literal=TRACKER_PROVICER=servicenow \
--from-literal=APP_FIELD=<Custom app label field> \
-n pelorus
```

#### Instance Config Jira

Note: By default JIRA exporter expects specific workflow to be used, where the issue needs to be `Resolved` with `resolutiondate` and all the relevant issues to be type of `Bug` with `Highest` priority with `app.kubernetes.io/name=<app_name>` label. This however can be customized to the orgaization needs by configuring `JIRA_JQL_SEARCH_QUERY`, `JIRA_RESOLVED_STATUS` and `APP_LABEL` options. Please refer to the [Failure Exporter ConfigMap Data Values](#failureconfigmap).

```yaml
exporters:
  instances:
  - app_name: failuretime-exporter
    exporter_type: failure
    env_from_secrets:
    - jira-secret
    env_from_configmaps:
    - pelorus-config
    - failuretime-config
```

#### Instance Config Github
```yaml
exporters:
  instances:
  - app_name: failuretime-exporter
    exporter_type: failure
    env_from_secrets:
    - github-issue-secret
    env_from_configmaps:
    - pelorus-config
    - failuretime-github-config
```

#### <a id="failureconfigmap"></a>ConfigMap Data Values
This exporter provides several configuration options, passed via `pelorus-config` and `failuretime-config` variables. User may define own ConfigMaps and pass to the committime exporter in a similar way.

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `PROVIDER` | no | Set the type of failure provider. One of `jira`, `servicenow` | `jira` |
| `LOG_LEVEL` | no | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `SERVER` | yes | URL to the Jira or ServiceNowServer  | unset  |
| `USER` | yes | Tracker Username | unset |
| `TOKEN` | yes | User's API Token | unset |
| `APP_LABEL` | no | Used in GitHub and JIRA only. Changes the label key used to identify applications  | `app.kubernetes.io/name`  |
| `APP_FIELD` | no | Required for ServiceNow, field used for the Application label. ex: "u_appName" | 'u_application' |
| `PROJECTS` | no | Used for Jira Exporter to query issues from a list of project keys. Comma separated string. ex: `PROJECTKEY1,PROJECTKEY2`. Value is ignored if `JIRA_JQL_SEARCH_QUERY` is defined. | unset |
| `PELORUS_DEFAULT_KEYWORD` | no | ConfigMap default keyword. If specified it's used in other data values to indicate "Default Value" should be used | `default` |
| `JIRA_JQL_SEARCH_QUERY` | no | Used for Jira Exporter to define custom JQL query to gather list issues. Ex: `type in ("Bug") AND priority in ("Highest","Medium") AND project in ("Project_1","Project_2")` | unset |
| `JIRA_RESOLVED_STATUS` | no | Used for Jira Exporter to define list Issue states that indicates whether issue is considered resolved. Comma separated string. ex: `Done,Closed,Resolved,Fixed` | unset |

### Github failure exporter details

The recommendation for utilizing the Github failure exporter is to define the Github token and Github projects.
The `TOKEN` should be defined in an OpenShift secret as described above.
The `PROJECTS` are best defined in the failure exporter ConfigMap. An example is found below.

```
kind: ConfigMap
metadata:
  name: failuretime-config
  namespace: pelorus
data:
  PROVIDER: "github"     # jira  |  jira, github, servicenow
  SERVER:                #       |  URL to the Jira or ServiceNowServer, can be overriden by env_from_secrets
  USER:                  #       |  Tracker Username, can be overriden by env_from_secrets
  TOKEN:                 #       |  User's API Token, can be overriden by env_from_secrets
  PROJECTS: "konveyor/todolist-mongo-go,konveyor/todolist-mariadb-go"
  APP_FIELD: "todolist"  #       |  This is optional for the Github failure exporter
```

The `PROJECTS` key is comma deliniated and formated at "Github_organization/Github_repository"
The `APP_FIELD` key may be used to associate the Github repository with a particular application

Any Github issue must be labeled as a "bug".  Any issue optionally can be labeled with a label associated
with a particular application.  If an application is not found it will default the app to the Github repository name.

An example of the output with the `APP_FIELD` for the [todolist-mongo-go repository](https://github.com/konveyor/todolist-mongo-go)  is found below:
```
05-25-2022 13:09:40 INFO     Collected failure_creation_timestamp{ app=todolist, issue_number=3 } 1652305808.0
05-25-2022 13:09:40 INFO     Collected failure_creation_timestamp{ app=todolist-mariadb-go, issue_number=4 } 1652462194.0
05-25-2022 13:09:40 INFO     Collected failure_creation_timestamp{ app=todolist, issue_number=3 } 1652394664.0
```

An example of not setting the `APP_FIELD` is here:
```
05-25-2022 13:16:14 INFO     Collected failure_creation_timestamp{ app=todolist-mongo-go, issue_number=3 } 1652305808.0
05-25-2022 13:16:14 INFO     Collected failure_creation_timestamp{ app=todolist-mariadb-go, issue_number=4 } 1652462194.0
05-25-2022 13:16:14 INFO     Collected failure_creation_timestamp{ app=todolist-mariadb-go, issue_number=3 } 1652394664.0
```

### ServiceNow failure exporter details

The integration with ServiceNow is configured to process Incident objects that have been resolved (stage=6).  Since there are not Tags in all versions of ServiceNow there may be a need to configure a custom field on the Incident object to provide an application name to match Openshift Labels.  The exporter uses the opened_at field for created timestamp and the resolved_at field for the resolution timestamp.  The exporter will traverse through all the incidents and when a resolved_at field is populated it will create a resolution record.

A custom field can be configure with the following steps:

- Navigate to an existing Incident
- Use the upper left Menu and select Configure -> Form Layout
- Create a new field (String, Table or reference a List)
- You can use the API Explorer to verify the name of the field to be used as the APP_FIELD
