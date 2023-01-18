# Failure Time Exporter

Failure time exporter captures the timestamp at which a failure occurred, in a production environment, and when it was resolved. It does this by parsing the information of when the issue was created, and closed, in the Issue Tracker(s).

Failure Time Exporter may be deployed with one of the [supported Issues Trackers](../Overview.md#issue-trackers). In one clusters' namespace there may be multiple instances of Failure Time Exporter, one for each provider (or each project). Each provider requires specific [configuration](#failureconfigmap).

<!-- For GitHub Issues and JIRA backends we require that all issues associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label, or custom label if it was configured via `APP_LABEL`. -->

## ConfigMap Data Values
This exporter provides several configuration options, passed via `pelorus-config` and `failuretime-config` variables. User may define own ConfigMaps and pass to the committime exporter in a similar way.

| Variable                  | Required | Explanation                                                                                                                                                                        | Default Value            |
|---------------------------|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------|
| `PROVIDER`                | no       | Set the type of failure provider. One of `jira`, `github`, `servicenow`                                                                                                            | `jira`                   |
| `LOG_LEVEL`               | no       | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`                                                                                                                      | `INFO`                   |
| `SERVER`                  | yes      | URL to the Jira or ServiceNowServer                                                                                                                                                | unset                    |
| `API_USER`                | yes      | Tracker Username                                                                                                                                                                   | unset                    |
| `TOKEN`                   | yes      | User's API Token                                                                                                                                                                   | unset                    |
| `APP_LABEL`               | no       | Used in GitHub and JIRA only. Changes the label key used to identify applications                                                                                                  | `app.kubernetes.io/name` |
| `APP_FIELD`               | no       | Required for ServiceNow, field used for the Application label. ex: "u_appName"                                                                                                     | 'u_application'          |
| `PROJECTS`                | no       | Used for Jira Exporter to query issues from a list of project keys. Comma separated string. ex: `PROJECTKEY1,PROJECTKEY2`. Value is ignored if `JIRA_JQL_SEARCH_QUERY` is defined. | unset                    |
| `PELORUS_DEFAULT_KEYWORD` | no       | ConfigMap default keyword. If specified it's used in other data values to indicate "Default Value" should be used                                                                  | `default`                |
| `JIRA_JQL_SEARCH_QUERY`   | no       | Used for Jira Exporter to define custom JQL query to gather list issues. Ex: `type in ("Bug") AND priority in ("Highest","Medium") AND project in ("Project_1","Project_2")`       | unset                    |
| `JIRA_RESOLVED_STATUS`    | no       | Used for Jira Exporter to define list Issue states that indicates whether issue is considered resolved. Comma separated string. ex: `Done,Closed,Resolved,Fixed`                   | unset                    |

## Github failure exporter details

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

## ServiceNow failure exporter details

The integration with ServiceNow is configured to process Incident objects that have been resolved (stage=6).  Since there are not Tags in all versions of ServiceNow there may be a need to configure a custom field on the Incident object to provide an application name to match Openshift Labels.  The exporter uses the opened_at field for created timestamp and the resolved_at field for the resolution timestamp.  The exporter will traverse through all the incidents and when a resolved_at field is populated it will create a resolution record.

A custom field can be configure with the following steps:

- Navigate to an existing Incident
- Use the upper left Menu and select Configure -> Form Layout
- Create a new field (String, Table or reference a List)
- You can use the API Explorer to verify the name of the field to be used as the APP_FIELD

## Configuring JIRA workflow(s)

> **Note:** By default JIRA exporter expects specific workflow to be used, where the monitored issues need to:
>
>* be type of `Bug`.
>* be of priority `Highest`.
>* be labeled with `app.kubernetes.io/name=<app_name>`.
>* be `Resolved` with `resolutiondate`.
>
>This however can be customized by configuring `JIRA_JQL_SEARCH_QUERY`, `JIRA_RESOLVED_STATUS` and `APP_LABEL` options as explained in the [Configuring JIRA workflow(s)](#configuring-jira-workflows).

For all JIRA configuration options refer to the [Failure Exporter ConfigMap Data Values](#failureconfigmap).

Jira issue:

In the Jira project issue settings, create a label with the text "app.kubernetes.io/name=todolist".

![jira_issue](../../img/jira_issue.png)

### Default JIRA workflow

Failure Time Exporter configured to work with JIRA issue tracking and project management software, by default will collect information about *all* of the Issues with the following attributes:

1. JIRA Issue to be type of `Bug` with the `Highest` priority.
2. The Resolved JIRA Issue must have `resolutiondate` field.

Optionally user may configure:

1. Pelorus to track only relevant JIRA projects by specyfing `PROJECTS` ConfigMap Data Value. This comma separated value may include either JIRA Project name or JIRA Project Key. Ensure the project key or project name exists in the JIRA, otherwise none of the metrics will get collected.
2. Issue labeled with the `app.kubernetes.io/name=<application_name>`, where `<application_name>` is a user defined application name to be monitored by Pelorus. This name needs to be consistent across other exporters, so the performance metrics presented in the Grafana dashboard are correct. Issues without such label are collected by the failure exporter with the application name: `unknown`.

### Example Failure Time Exporter ConfigMap with optional fields

Three JIRA projects to be monitored and custom application label to be used within JIRA Issues:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: custom-failure-config
  namespace: pelorus
data:
  PROVIDER: "jira"
  PROJECTS: "Testproject,SECONDPROJECTKEY,thirdproject"
  APP_LABEL: "my.app.label/myname"
```

### Custom JIRA workflow

The Failure Time Exporter(s) can be easily adjusted to adapt custom JIRA workflow(s), this includes:

1. Custom JIRA JQL query to find all matching issues to be tracked. *NOTE* in such case `PROJECTS` value is ignored, because user may or may not include `project` as part of the custom JQL query. More information is available at [Advanced Jira Query Language (JQL) site](https://support.atlassian.com/jira-service-management-cloud/docs/use-advanced-search-with-jira-query-language-jql/).

2. Custom label name to track `<application_name>`. Similarly to the previously explained example in the [Default JIRA workflow](#default-jira-workflow) section. 

3. Custom Resolved state(s). Moving JIRA Issue to one of those states reflects resolution date of an Issue, which is different from the default `resolutiondate` field.

### Example Failure Time Exporter ConfigMap for custom JIRA workflow

Custom JIRA query to collect all Issues with type of `Bug` that has one of the priorities `Highest` or `Medium` and is within JIRA project name `Sample` or `MYJIRAPROJ` project key name. Additionally each JIRA Issue should be labelled with the custom `my.company.org/appname=<application_name>` label. Pelorus expects the Issue to be marked as Resolved if the Issue is moved to one of the states: `Done`, `Closed` or `Resolved`.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: second-custom-failure-config
  namespace: pelorus
data:
  PROVIDER: "jira"
  JIRA_JQL_SEARCH_QUERY: 'type in ("Bug") AND priority in ("Highest","Medium") AND project in ("Sample","MYJIRAPROJ")'
  JIRA_RESOLVED_STATUS: 'Done,Closed,Resolved'
  APP_LABEL: "my.company.org/appname"
```

### Custom JIRA Failure Instance Config

User may deploy multiple Failure Time Exporter instances to gather metrics from multiple JIRA servers or different JIRA workflows. This is achieved by passing different ConfigMap for each instance.

Example ConfigMaps from the previous [Configuring JIRA workflow(s)](#configuring-jira-workflows) section may be used to deploy two separate instances. As shown in the below Pelorus configuration, each of the ConfigMap may be configured variously:

```yaml
exporters:
  instances:
  - app_name: custom-failure-exporter
    exporter_type: failure
    env_from_secrets:
    - my-jira-secret
    env_from_configmaps:
    - pelorus-config
    - custom-failure-config

  - app_name: second-custom-failure-exporter
    exporter_type: failure
    env_from_secrets:
    - my-jira-secret
    env_from_configmaps:
    - pelorus-config
    - second-custom-failure-config
```
