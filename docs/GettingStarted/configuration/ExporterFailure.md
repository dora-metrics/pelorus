# Failure Time Exporter

The job of the failure time exporter is to capture the timestamp at which a failure occurs in a production environment and when it is resolved.

Failure Time Exporter may be deployed with one of three backends, such as JIRA, GitHub Issues and ServiceNow. In one clusters' namespace there may be multiple instances of the Failure Time Exporter for each of the backends or/and watched projects.

Each of the backend requires specific [configuration](#failureconfigmap), that may be used via ConfigMap associated with the exporter instance.

For GitHub Issues and JIRA backends we require that all issues associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label, or custom label if it was configured via `APP_LABEL`.


## Instance Config JIRA

Note: By default JIRA exporter expects specific workflow to be used, where the issue needs to be `Resolved` with `resolutiondate` and all the relevant issues to be type of `Bug` with `Highest` priority with `app.kubernetes.io/name=<app_name>` label. This however can be customized to the orgaization needs by configuring `JIRA_JQL_SEARCH_QUERY`, `JIRA_RESOLVED_STATUS` and `APP_LABEL` options as explained in the [Configuring JIRA workflow(s)](#configuring-jira-workflows).

For all JIRA configuration options refer to the [Failure Exporter ConfigMap Data Values](#failureconfigmap).

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

## Instance Config Github
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

## <a id="failureconfigmap"></a>ConfigMap Data Values
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

# Github failure exporter details

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

# ServiceNow failure exporter details

The integration with ServiceNow is configured to process Incident objects that have been resolved (stage=6).  Since there are not Tags in all versions of ServiceNow there may be a need to configure a custom field on the Incident object to provide an application name to match Openshift Labels.  The exporter uses the opened_at field for created timestamp and the resolved_at field for the resolution timestamp.  The exporter will traverse through all the incidents and when a resolved_at field is populated it will create a resolution record.

A custom field can be configure with the following steps:

- Navigate to an existing Incident
- Use the upper left Menu and select Configure -> Form Layout
- Create a new field (String, Table or reference a List)
- You can use the API Explorer to verify the name of the field to be used as the APP_FIELD