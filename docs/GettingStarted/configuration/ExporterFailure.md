# Failure Time Exporter

Failure time exporter captures the timestamp at which a failure occurred, in a production environment, and when it was resolved. It does this by parsing the information of when the issue was created, and closed, in the Issue Tracker(s).

Failure Time Exporter may be deployed with one of the [supported Issues Trackers](../Overview.md#issue-trackers). In one clusters' namespace there may be multiple instances of Failure Time Exporter, one for each provider (or each project). Each provider requires specific [configuration](#failureconfigmap).

Each Failure time exporter configuration option must be placed under `spec.exporters.instances` in the Pelorus configuration object YAML file as in the example:

```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: example-configuration
spec:
  exporters:
    instances:
      - app_name: failure-exporter
        exporter_type: failure
        [...] # Failure time exporter configuration options
```

## Example

Configuration part of the Failure time exporter YAML file, with some non-default options:

```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: example-configuration
spec:
  exporters:
    instances:
      - app_name: failure-exporter
        exporter_type: failure
        env_from_secrets:
        - github-secret
        env_from_configmaps:
        - failure-config
        extraEnv:
          - name: PROVIDER
            value: github
          - name: PROJECTS
            value: github_user/repository
```

## Failure Time Exporter configuration options

This is the list of options that can be applied to `env_from_secrets`, `env_from_configmaps` and `extraEnv` section of a Failure time exporter.

| Variable | Required | Default Value |
|----------|----------|---------------|
| [PROVIDER](#provider) | no | `jira` |
| [LOG_LEVEL](#log_level) | no | `INFO` |
| [SERVER](#server) | yes | - |
| [API_USER](#api_user) | yes | - |
| [TOKEN](#token) | yes | - |
| [APP_LABEL](#app_label) | no | `app.kubernetes.io/name` |
| [APP_FIELD](#app_field) | no | `u_application` |
| [PROJECTS](#projects) | no | - |
| [PELORUS_DEFAULT_KEYWORD](#pelorus_default_keyword) | no | `default` |
| [JIRA_JQL_SEARCH_QUERY](#jira_jql_search_query) | no | - |
| [JIRA_RESOLVED_STATUS](#jira_resolved_status) | no | - |
| [GITHUB_ISSUE_LABEL](#github_issue_label) | no | bug |

###### PROVIDER

- **Required:** no
    - **Default Value:** jira
- **Type:** string

: Set the Issue Tracker provider for the failure exporter. One of `jira`, `github`, `servicenow`.

###### LOG_LEVEL

- **Required:** no
    - **Default Value:** INFO
- **Type:** string

: Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`.

###### SERVER

- **Required:** yes
    - Only applicable for [PROVIDER](#provider) set to `jira` or `servicenow`
- **Type:** string

: URL to the Jira or ServiceNow Server.

###### API_USER

- **Required:** yes
    - Only applicable for [PROVIDER](#provider) set to `jira` or `servicenow`
- **Type:** string

: Issue Tracker provider username.

###### TOKEN

- **Required:** yes
- **Type:** string

: Issue Tracker provider API Token.

###### APP_LABEL

- **Required:** no
    - Only applicable for [PROVIDER](#provider) set to `jira` or `github`
    - **Default Value:** app.kubernetes.io/name
- **Type:** string

: Changes the label used to identify applications.

###### APP_FIELD

- **Required:** no
    - Only applicable for [PROVIDER](#provider) set to `servicenow`
    - **Default Value:** u_application
- **Type:** string

: Field used for the Application label.

###### PROJECTS

- **Required:** no
    - Only applicable for [PROVIDER](#provider) set to `jira` or `github`
- **Type:** comma separated list of strings

: * Used by Jira to define which projects (keys or names) to monitor. Value is ignored if [JIRA_JQL_SEARCH_QUERY](#jira_jql_search_query) is defined.

: * Used by GitHub to define which repositories' issues to monitor.

###### PELORUS_DEFAULT_KEYWORD

- **Required:** no
    - **Default Value:** default
- **Type:** string

: Used only when configuring instance using ConfigMap. It is the ConfigMap value that represents `default` value. If specified it's used in other data values to indicate "Default Value" should be used.

###### JIRA_JQL_SEARCH_QUERY

- **Required:** no
    - Only applicable for [PROVIDER](#provider) set to `jira`
- **Type:** string

: Used to define custom JQL query to gather issues. More information is available at [Advanced Jira Query Language (JQL) site](https://support.atlassian.com/jira-service-management-cloud/docs/use-advanced-search-with-jira-query-language-jql/).

###### JIRA_RESOLVED_STATUS

- **Required:** no
    - Only applicable for [PROVIDER](#provider) set to `jira`
- **Type:** string

: Defines issue status (comma separated) that indicates if issue is resolved.

###### GITHUB_ISSUE_LABEL

- **Required:** no
    - Only applicable for [PROVIDER](#provider) set to `github`
    - **Default Value:** bug
- **Type:** string

: Defines a custom label to be used in GitHub issues to identify the ones to be monitored.

## Configuring Jira

### Default workflow

By default, Failure Time Exporter(s) configured to work with Jira expects specific workflow to be used, where the monitored issues need to:

* Be in any of the projects within the [SERVER](#server).

* Be of type `Bug` and of priority `Highest`.

* Be labeled with `app.kubernetes.io/name=app_name`, where **app_name** is the name of one of the applications being monitored.

    > **NOTE:** Issues without such label are collected with the application name set to **unknown**.

* Be `Resolved` with `resolutiondate`.

### Custom workflow

Failure Time Exporter(s) configured to work with Jira can be easily adjusted to adapt to custom workflow(s), like:

* Custom selected projects within the [SERVER](#server), using [PROJECTS](#projects).

* Custom Jira JQL query to find all matching issues, using [JIRA_JQL_SEARCH_QUERY](#jira_jql_search_query).

    > **NOTE:** in such case [PROJECTS](#projects) value is ignored.

* Custom label to track application named **app_name**, using [APP_LABEL](#app_label).

* Custom issue resolved status, using [JIRA_RESOLVED_STATUS](#jira_resolved_status).

### Examples

In the following examples, we consider that `env_from_secrets` contains both [API_USER](#api_user) and [TOKEN](#token).

#### Custom projects and label

In this example, Failure Time Exporter configured to work with Jira will monitor only issues:

* in **example_server_url** server.
* in **Testproject**, **SECONDPROJECTKEY** or **thirdproject** projects.
* of type **Bug**.
* with priority **Hightest**.
* labeled with **my.app.label/myname** or **my.app.label/myname=app_name**.
* And only issues that have `resolutiondate` will be considered resolved.

```yaml
[...]
      - app_name: jira-failure-exporter
        exporter_type: failure
        env_from_secrets:
        - jira-secret
        extraEnv:
          - name: SERVER
            value: example_server_url
          - name: PROJECTS
            value: Testproject,SECONDPROJECTKEY,thirdproject
          - name: APP_LABEL
            value: my.app.label/myname
[...]
```

#### Custom JQL, resolved states and label

In this example, Failure Time Exporter configured to work with Jira will monitor only issues:

* in **example_server_url** server.
* in **Sample**  or **MYJIRAPROJ** projects.
* of type **Bug**.
* with priority **Hightest** or **Medium**.
* labeled with **my.company.org/appname** or **my.company.org/appname=app_name**.
* And only issues that have their status changed to **DONE**, **CLOSED** or **RESOLVED** will be considered resolved.

```yaml
[...]
      - app_name: jira-failure-exporter
        exporter_type: failure
        env_from_secrets:
        - jira-secret
        extraEnv:
          - name: SERVER
            value: example_server_url
          - name: JIRA_JQL_SEARCH_QUERY
            value: type in ("Bug") AND priority in ("Highest","Medium") AND project in ("Sample","MYJIRAPROJ")
          - name: APP_LABEL
            value: my.company.org/appname
          - name: JIRA_RESOLVED_STATUS
            value: Done,Closed,Resolved
[...]
```

#### Multiple Jira servers

In this example, 2 Failure Time Exporters are configured to work with Jira, each in a different server.

`jira-failure-exporter-1` will monitor only issues:

* in any of the projects within the **example_server_url_1** server.

`jira-failure-exporter-2` will monitor only issues:

* in any of the projects within the **example_server_url_2** server.

And both will monitor only issues:

* of type **Bug**.
* with priority **Hightest**.
* labeled with **my.app.label/myname** or **my.app.label/myname=app_name**.
* And only issues that have `resolutiondate` will be considered resolved.

```yaml
[...]
      - app_name: jira-failure-exporter-1
        exporter_type: failure
        env_from_secrets:
        - jira-secret
        extraEnv:
          - name: SERVER
            value: example_server_url_1
      - app_name: jira-failure-exporter-2
        exporter_type: failure
        env_from_secrets:
        - jira-secret
        extraEnv:
          - name: SERVER
            value: example_server_url_2
[...]
```

## Configuring GitHub

### Default workflow

By default, Failure Time Exporter(s) configured to work with GitHub expects specific workflow to be used, where the monitored issues need to:

* Be in the repositories listed in [PROJECTS](#projects).

* Be labeled with `bug`.

* Be labeled with `app.kubernetes.io/name=app_name`, where **app_name** is the name of one of the applications being monitored.

    > **NOTE:** Issues without such label are collected with the application name set to the **repository name**.

### Custom workflow

Failure Time Exporter(s) configured to work with GitHub can be easily adjusted to adapt to custom workflow(s), like:

* Custom label to track monitored issues, using [GITHUB_ISSUE_LABEL](#github_issue_label).

* Custom label to track application named **app_name**, using [APP_LABEL](#app_label).

### Examples

In the following examples, we consider that `env_from_secrets` contains [TOKEN](#token).

#### Multiple GitHub repositories

In this example, Failure Time Exporter configured to work with GitHub will monitor only issues:

* in **github_user/repository1** or **github_user/repository2** repositories' issues.
* labeled with **bug**.
* labeled with **important** or **important=app_name**.
* And only issues that are closed, will be considered resolved.

```yaml
[...]
      - app_name: github-failure-exporter
        exporter_type: failure
        env_from_secrets:
        - github-secret
        extraEnv:
          - name: PROVIDER
            value: github
          - name: APP_LABEL
            value: important
          - name: PROJECTS
            value: github_user/repository1,github_user/repository2
[...]
```

## Configuring ServiceNow

### Default workflow

By default, Failure Time Exporter(s) configured to work with ServiceNow expects specific workflow to be used, where the monitored incidents need to:

* Be in the [SERVER](#server).

* Have the field `u_application`, where it should store the name of one of the applications being monitored.

    > **NOTE:** Since there are not tags in all versions of ServiceNow, there is the need to configure a custom field on the Incident object to provide an application name to match OpenShift Labels.

* And only incidents that are `stage=6` (when a `resolved_at` field is populated) will be considered resolved.

### Custom workflow

Failure Time Exporter(s) configured to work with ServiceNow can be easily adjusted to adapt to custom workflow(s), like:

* Have the field [APP_FIELD](#app_field), where it should store the name of one of the applications being monitored.

A custom field can be configure with the following steps:

- Navigate to an existing Incident.
- Use the upper left Menu and select Configure -> Form Layout.
- Create a new field (String, Table or reference a List).