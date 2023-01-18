# Failure Time Exporter

Failure time exporter captures the timestamp at which a failure occurred, in a production environment, and when it was resolved. It does this by parsing the information of when the issue was created, and closed, in the Issue Tracker(s).

Failure Time Exporter may be deployed with one of the [supported Issues Trackers](../Overview.md#issue-trackers). In one clusters' namespace there may be multiple instances of Failure Time Exporter, one for each provider (or each project). Each provider requires specific [configuration](#failureconfigmap).

## List of all configuration options

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

### PROVIDER

- **Required:** no
    - **Default Value:** jira
- **Type:** string

Set the Issue Tracker provider for the failure exporter. One of `jira`, `github`, `servicenow`.

### LOG_LEVEL

- **Required:** no
    - **Default Value:** INFO
- **Type:** string

Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`.

### SERVER

(JUST FOR JIRA AND SERVICENOW ISSUE TRACKERS)

- **Required:** yes
- **Type:** string

URL to the Jira or ServiceNow Server.

### API_USER

(JUST FOR JIRA AND SERVICENOW ISSUE TRACKERS)

- **Required:** yes
- **Type:** string

Issue Tracker provider username.

### TOKEN

- **Required:** yes
- **Type:** string

Issue Tracker provider API Token.

### APP_LABEL

(JUST FOR JIRA AND GITHUB ISSUE TRACKERS)

- **Required:** no
    - **Default Value:** app.kubernetes.io/name
- **Type:** string

Changes the label used to identify applications.

### APP_FIELD

(JUST FOR SERVICENOW ISSUE TRACKER)

- **Required:** no
    - **Default Value:** u_application
- **Type:** string

Required for ServiceNow, field used for the Application label. ex: "u_appName".

### PROJECTS

(JUST FOR JIRA AND GITHUB ISSUE TRACKERS)

- **Required:** no
- **Type:** string

Comma separated.

* Used by Jira to define which projects (keys or names) to monitor. Value is ignored if [JIRA_JQL_SEARCH_QUERY](#jira_jql_search_query) is defined. Ensure the project(s) exists, otherwise none of the metrics will get collected.

* Used by GitHub to define which repositories' issues to monitor.

### PELORUS_DEFAULT_KEYWORD

- **Required:** no
    - **Default Value:** default
- **Type:** string

ConfigMap default keyword. If specified, it is used in other data values to indicate "Default Value" should be used.

### JIRA_JQL_SEARCH_QUERY

(JUST FOR JIRA ISSUE TRACKER)

- **Required:** no
- **Type:** string

Used to define custom JQL query to gather issues. More information is available at [Advanced Jira Query Language (JQL) site](https://support.atlassian.com/jira-service-management-cloud/docs/use-advanced-search-with-jira-query-language-jql/).

### JIRA_RESOLVED_STATUS

(JUST FOR JIRA ISSUE TRACKER)

- **Required:** no
- **Type:** string

Defines issue status (comma separated) that indicates if issue is resolved.


## Configuring GitHub

Example Github issue:

Create an issue, and create a Github issue label: "app.kubernetes.io/name=todolist".

![github_issue](../../img/github_issue.png)

The recommendation for utilizing the Github failure exporter is to define the Github token and Github projects.
The `TOKEN` should be defined in an OpenShift secret as described above.
The `PROJECTS` are best defined in the failure exporter ConfigMap. An example is found below.

```yaml
kind: ConfigMap
metadata:
  name: failuretime-config
  namespace: pelorus
data:
  PROVIDER: "github"     # jira  |  jira, github, servicenow
  SERVER:                #       |  URL to the Jira or ServiceNowServer, can be overridden by env_from_secrets
  API_USER:                  #       |  Tracker Username, can be overridden by env_from_secrets
  TOKEN:                 #       |  User's API Token, can be overridden by env_from_secrets
  PROJECTS: "konveyor/todolist-mongo-go,konveyor/todolist-mariadb-go"
  APP_FIELD: "todolist"  #       |  This is optional for the Github failure exporter
```

The `PROJECTS` key is comma delimited and formatted at "Github_organization/Github_repository"
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

## Configuring ServiceNow

The integration with ServiceNow is configured to process Incident objects that have been resolved (stage=6).  Since there are not Tags in all versions of ServiceNow there may be a need to configure a custom field on the Incident object to provide an application name to match Openshift Labels.  The exporter uses the opened_at field for created timestamp and the resolved_at field for the resolution timestamp.  The exporter will traverse through all the incidents and when a resolved_at field is populated it will create a resolution record.

A custom field can be configure with the following steps:

- Navigate to an existing Incident
- Use the upper left Menu and select Configure -> Form Layout
- Create a new field (String, Table or reference a List)
- You can use the API Explorer to verify the name of the field to be used as the APP_FIELD

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
