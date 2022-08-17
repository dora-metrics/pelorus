# Configuration

## Configuring the Pelorus stack

The Pelorus stack (Prometheus, Grafana, Thanos, etc.) is configured by changing the `values.yaml` file that is passed to Helm. The recommended practice is to make a copy of the [values.yaml](https://GitHub.com/konveyor/pelorus/blob/master/charts/pelorus/values.yaml) file and [charts/pelorus/configmaps/](https://GitHub.com/konveyor/pelorus/tree/master/charts/pelorus/configmaps) directory, and store it in a local configuration repo for safe development. Once tested, update the `charts/pelorus/configmaps` files with `values.yaml` and apply the changes.

```
oc apply -f `myclusterconfigs/pelorus/configmaps
helm upgrade pelorus charts/pelorus --namespace pelorus --values myclusterconfigs/pelorus/values.yaml
```

## Configurations
The following configurations may be made through the `values.yaml` file:

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `openshift_prometheus_htpasswd_auth` | yes | htpasswd file contents used for basic Prometheus user authentication. | User: `internal`, Password: `changeme` |
| `openshift_prometheus_basic_auth_pass` | yes | Grafana password for its Prometheus datasource. Must match htpassword. | `changme` |
| `custom_ca` | no | Determines if the cluster serves custom signed certificates for ingress (e.g. router certs). `true` will load the custom certs via the [certificate injection method](https://docs.openshift.com/container-platform/4.4/networking/configuring-a-custom-pki.html#certificate-injection-using-operators_configuring-a-custom-pki)  | `false`  |
| `exporters` | no | Specifies which exporters to install. See [Configuring Exporters](#configuring-exporters). | Installs deploytime exporter only. |

## Configuring exporters overview
The _exporter_ data collection application pulls data from various tools and platforms so it can be consumed by Pelorus dashboards. Each exporter gets deployed individually alongside the core Pelorus stack.


There are currently three _exporter_ types which need to be specified using the `exporters.instances.exporter_type` value:
* `deploytime`
* `failure`
* `comittime`

Exporters are deployed using a list of `exporters.instances` inside the `values.yaml` file that correspond to the OpenShift ConfigMap configurations in the `charts/pelorus/configmaps/` directory. Some exporters also require secrets be created when integrating with external tools and platforms. A sample exporter configuration may look like this:

```yaml
exporters:
  instances:
  - app_name: deploytime-exporter
    exporter_type: deploytime
    env_from_configmaps:
    - pelorus-config
    - deploytime-config
```

A single exporter can be deployed multiple times to gather data from different sources. For example, deploying two instances of the Commit Time Exporter to pull commit data from both GitHub and a private GitHub Enterprise instance.

Each exporter has a unique set of environment variables to configure its integrations and behavior. These variables are set by using example ConfigMap object configurations similar to the Kubernetes secrets and listing them under `env_from_configmaps` or under `env_from_secrets` accordingly.

```yaml
exporters:
  instances:
  - app_name: committime-GitHub
    exporter_type: comittime
    env_from_secrets:
    - GitHub-credentials
    env_from_configmaps:
    - pelorus-config
    - committime-config

  - app_name: committime-gh-enterprise
    exporter_type: comittime
    env_from_secrets:
    - GitHub-enterprise-credentials
    env_from_configmaps:
    - pelorus-config
    - comittime-enterprise-config
```

### Exporter ConfigMap configuration values
Each exporter is configured using ConfigMap objects. Each ConfigMap must be in a separate file and must be applied to the cluster before deploying the Pelorus Helm chart.

> **Important:**  Store the ConfigMap folder outside of the local Pelorus Git repository and modify accordingly.

ConfigMap can be applied individually or all together:
```shell
# Only deploytime ConfigMap
oc apply -f charts/pelorus/configmaps/deploytime.yaml

# All at once
oc apply -f charts/pelorus/configmaps/
```

This is an example ConfigMap for the `deploytime-exporter` with the unique name `deploytime-config`:
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

### Authentication to remote services
Pelorus exporters use `personal access tokens` when authentication is required. It is recommended to configure the Pelorus exporters with authentication using the `TOKEN` key to avoid connection rate limiting and access restrictions.

See [GitHub Personal Access Tokens](https://docs.GitHub.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) for more information about personal access tokens.

* [Jira / Bitbucket Personal Access Tokens](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)
* [Gitlab Personal Access Tokens](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
* [Microsoft Azure DevOps Tokens](https://docs.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops&tabs=Windows)
* [Gitea Tokens](https://docs.gitea.io/en-us/api-usage/#generating-and-listing-api-tokens)

Use Openshift secrets to store a personal access token securely and make it available to Pelorus to use for all of the exporters. The following is an example for the committime exporter in GitHub.

```shell
oc create secret generic GitHub-secret --from-literal=TOKEN=<personal access token> -n pelorus
```

A Pelorus exporter can require additional information to collect data such as the remote `GIT_API` or `USER` information. It is recommended to consult the requirements for each Pelorus exporter in this guide and include the additional key/value information in the Openshift secret. An API example is `GitHub.mycompany.com/api/v3` or `https://gitea.mycompany.com`.

CLI commands can also be substituted with secret templates. Example files can be found [here](https://GitHub.com/konveyor/pelorus/tree/master/charts/pelorus/secrets).

Here is an example of creating a secret containing the Git username, token, and sample API.

```shell
oc create secret generic GitHub-secret --from-literal=API_USER=<username> --from-literal=TOKEN=<personal access token> --from-literal=GIT_API=<api> -n pelorus
```
Example of creating a secret in Jira.
```shell
oc create secret generic jira-secret \
--from-literal=SERVER=<Jira Server> \
--from-literal=API_USER=<username/e-mail> \
--from-literal=TOKEN=<personal access token> \
-n pelorus
```
Example of creating a secret in ServiceNow.
```shell
oc create secret generic snow-secret \
--from-literal=SERVER=<ServiceNow Server> \
--from-literal=API_USER=<username> \
--from-literal=TOKEN=<personal access token> \
--from-literal=TRACKER_PROVICER=servicenow \
--from-literal=APP_FIELD=<Custom app label field> \
-n pelorus
```

### Labels
Labels are key/value pairs that are attached to objects such as pods. They are intended to be used to specify identifying attributes of objects that are meaningful and relevant to users and Pelorus.

The commit time, deploy time, and failure exporters all rely on labels to identify the application that is associated with an object.  The object can include a build, build configuration, deployment, or issue.

The default Pelorus label is: `app.kubernetes.io/name=<app_name>` where
`app_name` is the name of the application(s) being monitored. The label can be customized by setting the `APP_LABEL` variable to a custom value.

An example may be to override the APP_LABEL for the failure exporter to indicate a production bug or issue. The `APP_LABEL` with the value `production_issue/name` may give more context than `app.kubernetes.io/name`. In this case, the GitHub issue would be labeled with `production_issue/name=todolist`.

Example Failure exporter config:
```
- app_name: failure-exporter
  exporter_type: failure
  env_from_secrets:
  - GitHub-secret
  extraEnv:
  - name: LOG_LEVEL
    value: DEBUG
  - name: PROVIDER
    value: GitHub
  - name: PROJECTS
    value: konveyor/mig-demo-apps,konveyor/oadp-operator
  - name: APP_LABEL
    value: production_issue/name
```

> **Warning** If the application label is not properly configured, Pelorus will not collect data for that object.

In the following examples an application named [todolist](https://GitHub.com/konveyor/mig-demo-apps/blob/master/apps/todolist-mongo-go/mongo-persistent.yaml) is being monitored.

Example BuildConfig:
```
- kind: BuildConfig
  apiVersion: build.openshift.io/v1
  metadata:
    name: todolist
    namespace: mongo-persistent
    labels:
      app.kubernetes.io/name: todolist
```

Example DeploymentConfig:
```
- apiVersion: apps.openshift.io/v1
  kind: DeploymentConfig
  metadata:
    name: todolist
    namespace: mongo-persistent
    labels:
      app: todolist
      app.kubernetes.io/name: todolist
      application: todolist
      deploymentconfig: todolist-mongo-go
```

Example ReplicaSet:
```
replicas: 1
template:
  metadata:
    creationTimestamp:
    labels:
      e2e-app: "true"
      application: todolist
      deploymentconfig: todolist-mongo-go
      app.kubernetes.io/name: todolist
```

Example Application via the CLI:
```
oc -n mongo-persistent new-app todolist -l "app.kubernetes.io/name=todolist"
```

**Example GitHub issue**

Create an issue and create a GitHub issue label: "app.kubernetes.io/name=todolist".  Here is a working [example](https://GitHub.com/konveyor/mig-demo-apps/issues/82):

![GitHub_issue](img/GitHub_issue.png)

**Example Jira issue**

Create a label in the Jira project issue settings with the text "app.kubernetes.io/name=todolist".

![jira_issue](img/jira_issue.png)

## Annotated binary (local) source build support
The Commit Time Exporter may be used in conjunction with builds **where values required to gather commit time from the source repository are missing**. In these cases each build is required to be annotated with two values allowing the Commit Time Exporter to calculate metrics from the build.

Annotate the build with the following commands:
```shell
oc annotate build <build-name> -n <namespace> --overwrite io.openshift.build.commit.id=<commit_hash>

oc annotate build <build-name> -n <namespace> --overwrite io.openshift.build.source-location=<repo_uri>
```

Custom annotation names may also be configured using ConfigMap Data Values.

> **Note:** The requirement to label the build with `app.kubernetes.io/name=&lt;app_name>` for the annotated builds applies.

### Example workflow for an OpenShift binary build:

* Sample Application

```
cat app.py
#!/usr/bin/env python3
print("Hello World")
```

* Binary build steps

```
NS=binary-build
NAME=python-binary-build
oc create namespace "${NS}"
oc new-build python --name="${NAME}" --binary=true -n "${NS}"  -l "app.kubernetes.io/name=${NAME}"
oc start-build "bc/${NAME}" --from-file=./app.py --follow -n "${NS}"
oc get builds -n "${NS}"
oc -n "${NS}" annotate build "${NAME}-1" --overwrite \
io.openshift.build.commit.id=7810f2a85d5c89cb4b17e9a3208a311af65338d8 \
io.openshift.build.source-location=http://github.com/konveyor/pelorus
oc -n "${NS}" new-app "${NAME}" -l "app.kubernetes.io/name=${NAME}"
```

#### Additional examples

There are many ways to build and deploy applications in OpenShift.  Additional examples of how to annotate builds such that Pelorus will properly discover the commit metadata can be found in the  [Pelorus tekton demo](https://github.com/konveyor/pelorus/tree/master/demo)

## Configuring exporters details

#### An example workflow for an OpenShift binary build:

* Sample Application

```
cat app.py 
#!/usr/bin/env python3
print("Hello World")
```

* Binary build steps

```
NS=binary-build
NAME=python-binary-build

oc create namespace "${NS}"

oc new-build python --name="${NAME}" --binary=true -n "${NS}"  -l "app.kubernetes.io/name=${NAME}"
oc start-build "bc/${NAME}" --from-file=./app.py --follow -n "${NS}"

oc get builds -n "${NS}"
oc -n "${NS}" annotate build "${NAME}-1" --overwrite \
io.openshift.build.commit.id=7810f2a85d5c89cb4b17e9a3208a311af65338d8 \
io.openshift.build.source-location=http://github.com/konveyor/pelorus

oc -n "${NS}" new-app "${NAME}" -l "app.kubernetes.io/name=${NAME}"
```


#### Additional examples

There are many ways to build and deploy applications in OpenShift.  Additional examples of how to annotate builds such that Pelorus will properly discover the commit metadata can be found in the  [Pelorus tekton demo](https://github.com/konveyor/pelorus/tree/master/demo)

## Configuring Exporters Details

### Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

We require that all builds associated with a particular application be labeled with the same `app.kubernetes.io/name=<app_name>` label.

Currently we support GitHub and GitLab, with BitBucket coming soon. Open an issue or a pull request to add support for additional Git providers!

#### Instance config

```yaml
exporters:
  instances:
  - app_name: committime-exporter
    exporter_type: committime
    env_from_secrets:
    - GitHub-secret
    env_from_configmaps:
    - pelorus-config
    - committime-config
```

#### ConfigMap Data Values

This exporter provides several configuration options that are passed using `pelorus-config` and `committime-config` variables. Users can define their own ConfigMaps and pass them to the committime exporter in a similar way.

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `API_USER` | yes | User's GitHub username | unset |
| `TOKEN` | yes | User's GitHub API Token | unset |
| `GIT_API` | no | GitHub, Gitea or Azure DevOps API FQDN. Allows override for Enterprise users. Currently only applicable to `GitHub`, `gitea` and `azure-devops` provider types. | `api.GitHub.com`, or `https://try.gitea.io`. No default for Azure DevOps. |
| `GIT_PROVIDER` | no | Set Git provider type. Can be `GitHub`, `gitlab`, or `bitbucket` | `GitHub` |
| `LOG_LEVEL` | no | Set the log level. Select one: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `APP_LABEL` | no | Changes the label key used to identify applications.  | `app.kubernetes.io/name`  |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. Ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
| `PELORUS_DEFAULT_KEYWORD` | no | ConfigMap default keyword. Select to use in other data values to indicate `Default Value` should be used | `default` |
| `COMMIT_HASH_ANNOTATION` | no | Annotation name associated with the build hash used to calculate commit time. | `io.openshift.build.commit.id` |
| `COMMIT_REPO_URL_ANNOTATION` | no | Annotation name associated with the build from which GIT repository URL is used to calculate commit time. | `io.openshift.build.source-location` |


## Configuring the Deploy Time Exporter
The Deploy Time Exporter captures the timestamp of a deployment in a production environment.

> **Important:** All deployments associated with a particular application must be labeled with the same `app.kubernetes.io/name=&lt;app_name>` label.

**Instance configuration**

```yaml
exporters:
  instances:
  - app_name: deploytime-exporter
    exporter_type: deploytime
    env_from_configmaps:
    - pelorus-config
    - deploytime-config
```

## ConfigMap Data Values Exporter
The ConfigMap Data Values Exporter provides several configuration options that are passed using `pelorus-config` and `deploytime-config` variables. Users can define custom ConfigMaps and pass them to the Commit Time Exporter in a similar way.

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `LOG_LEVEL` | no | Set the log level. Select one: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `APP_LABEL` | no | Changes the label key used to identify applications.  | `app.kubernetes.io/name`  |
| `PROD_LABEL` | no | Changes the label key used to identify namespaces that are considered production environments. | unset; matches all namespaces |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. Ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
| `PELORUS_DEFAULT_KEYWORD` | no | ConfigMap default keyword. Select to use in other data values to indicate `Default Value` should be used | `default` |

### Configuring the Failure Time Exporter
The Failure Time Exporter captures the timestamp of a failure in a production environment and when it is resolved.

Failure Time Exporter may be deployed with one of three backends: JIRA, GithHub Issues, and ServiceNow. One clusters' namespace can have multiple instances of the Failure Time Exporter for each backend and/or watched projects.

Each of the backends requires specific [configurations](#failureconfigmap) using the ConfigMap associated with the exporter instance.

> **Important:** All GitHub Issues and JIRA backend issues associated with a particular application must be labelled with the same `app.kubernetes.io/name=&lt;app_name>` label, or a custom label if it was configured via `APP_LABEL`.


#### Instance Config Jira Exporter
The Instance Config JIRA Exporter expects a specific workflow be used when the issue needs to be `Resolved` with `resolutiondate` and all the relevant issues to be a `Bug` with the `Highest` priority with the `app.kubernetes.io/name=&lt;app_name>` label.

This exporter can be customized to orgaizational needs by configuring `JIRA_JQL_SEARCH_QUERY`, `JIRA_RESOLVED_STATUS` and `APP_LABEL` options. Refer to the [Failure Exporter ConfigMap Data Values](https://pelorus.readthedocs.io/en/latest/Configuration/#failureconfigmap).

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

**Instance Config GitHub**
```yaml
exporters:
  instances:
  - app_name: failuretime-exporter
    exporter_type: failure
    env_from_secrets:
    - GitHub-issue-secret
    env_from_configmaps:
    - pelorus-config
    - failuretime-GitHub-config
```

#### <a id="failureconfigmap"></a>ConfigMap Data Values
This exporter provides several configuration options, passed via `pelorus-config` and `failuretime-config` variables. Users can define their own ConfigMaps and pass them to the Commit Time Exporter in a similar way.

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `PROVIDER` | no | Set the type of failure provider. Select one: `jira`, `servicenow` | `jira` |
| `LOG_LEVEL` | no | Set the log level. Select one: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `SERVER` | yes | URL to the Jira or ServiceNowServer.  | unset  |
| `API_USER` | yes | Tracker Username | unset |
| `TOKEN` | yes | User's API Token | unset |
| `APP_LABEL` | no | Used in GitHub and JIRA only. Changes the label key used to identify applications.  | `app.kubernetes.io/name`  |
| `APP_FIELD` | no | Required for ServiceNow, field used for the Application label. ex: "u_appName" | 'u_application' |
| `PROJECTS` | no | Used for Jira Exporter to query issues from a list of project keys. Comma separated string. Ex: `PROJECTKEY1,PROJECTKEY2`. Value is ignored if `JIRA_JQL_SEARCH_QUERY` is defined. | unset |
| `PELORUS_DEFAULT_KEYWORD` | no | ConfigMap default keyword. Select to use in other data values to indicate `Default Value` should be used. | `default` |
| `JIRA_JQL_SEARCH_QUERY` | no | Used for Jira Exporter to define custom JQL query to gather list issues. Ex: `type in ("Bug") AND priority in ("Highest","Medium") AND project in ("Project_1","Project_2")` | unset |
| `JIRA_RESOLVED_STATUS` | no | Used for Jira Exporter to define list Issue states that indicate whether issue is considered resolved. Comma separated string. Ex: `Done,Closed,Resolved,Fixed` | unset |

### GitHub Failure Exporter details
Use the GitHub Failure Exporter to define the GitHub token and GitHub projects. The `TOKEN` should be defined in an OpenShift secret as described above, and the `PROJECTS` are defined in the Failure Exporter ConfigMap. This is an example of the GitHub Failure Exporter.

```
kind: ConfigMap
metadata:
  name: failuretime-config
  namespace: pelorus
data:
  PROVIDER: "GitHub"     # jira  |  jira, GitHub, servicenow
  SERVER:                #       |  URL to the Jira or ServiceNowServer, can be overriden by env_from_secrets
  API_USER:                  #       |  Tracker Username, can be overriden by env_from_secrets
  TOKEN:                 #       |  User's API Token, can be overriden by env_from_secrets
  PROJECTS: "konveyor/todolist-mongo-go,konveyor/todolist-mariadb-go"
  APP_FIELD: "todolist"  #       |  This is optional for the GitHub failure exporter
```

The `PROJECTS` key is comma deliniated and formated at "GitHub_organization/GitHub_repository". The `APP_FIELD` key can be used to associate the GitHub repository with a particular application

Any GitHub issue must be labeled as a `bug` and can optionally have a label associated with a particular application. If an application is not found, it will default the app to the GitHub repository name.

This is an example of the output with the `APP_FIELD` for the [todolist-mongo-go repository](https://GitHub.com/konveyor/todolist-mongo-go).
```
05-25-2022 13:09:40 INFO     Collected failure_creation_timestamp{ app=todolist, issue_number=3 } 1652305808.0
05-25-2022 13:09:40 INFO     Collected failure_creation_timestamp{ app=todolist-mariadb-go, issue_number=4 } 1652462194.0
05-25-2022 13:09:40 INFO     Collected failure_creation_timestamp{ app=todolist, issue_number=3 } 1652394664.0
```

This is an example of not setting the `APP_FIELD`.
```
05-25-2022 13:16:14 INFO     Collected failure_creation_timestamp{ app=todolist-mongo-go, issue_number=3 } 1652305808.0
05-25-2022 13:16:14 INFO     Collected failure_creation_timestamp{ app=todolist-mariadb-go, issue_number=4 } 1652462194.0
05-25-2022 13:16:14 INFO     Collected failure_creation_timestamp{ app=todolist-mariadb-go, issue_number=3 } 1652394664.0
```

### ServiceNow Failure Exporter details
ServiceNow integration is configured to process resolved (stage=6) Incident objects. Because ServiceNow does not have tags in all versions, there may be a need to configure a custom field on the Incident object to provide an application name to match Openshift Labels. The exporter uses the `opened_at` field for a created timestamp and the `resolved_at` field for the resolution timestamp. The exporter monitors all incidents and will create a resolution record when a `resolved_at` field is populated.

A custom field can be configured with the following steps:
1. Navigate to an existing Incident.
2. In the upper left menu, click **Configure**, then **Form Layout**.
3. Create a new field (String, Table or reference a List).
4. Verify the APP_FIELD name using the API Explorer.
