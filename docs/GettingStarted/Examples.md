In the following sections, we present example configurations for a variety of Git Providers and Issue Trackers combinations. Change the values between `<>` to **your** values.

## Bitbucket & Jira

In this example, we use Bitbucket as the Git provider and Jira as the issue tracker.

> **Note:** Only issues labeled with `bug` and `app.kubernetes.io/name=<application_name>` will be tracked by failure exporter.

```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: bitbucket-jira-example-configuration
spec:
  exporters:
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
        extraEnv:
          - name: NAMESPACES
            value: <namespace_1,namespace_2>
      - app_name: committime-exporter
        exporter_type: committime
        extraEnv:
          - name: GIT_PROVIDER
            value: bitbucket
          - name: NAMESPACES
            value: <namespace_1,namespace_2>
          - name: API_USER
            value: <bitbucket_user>
          - name: TOKEN
            value: <bitbucket_token>
      - app_name: failure-exporter
        exporter_type: failure
        extraEnv:
          - name: API_USER
            value: <jira_username>
          - name: TOKEN
            value: <jira_token>
          - name: SERVER
            value: <jira_url>
          - name: PROJECTS
            value: <jira_project_1,jira_project_2>
```

Instead of adding `PROJECTS` to the `extraEnv:` section, it is possible to add `JIRA_JQL_SEARCH_QUERY` and `JIRA_RESOLVED_STATUS`. Check CONFIGURATION...

## GitHub

In this example, we use GitHub both as the Git provider and the Issue tracker.

> **NOTE:** Due to API rate limits for GitHub API, the TOKEN for Commit time and Failure Exporters must be set in `extraEnv` even for public repositories.

> **Note:** Only issues labeled with `bug` and `app.kubernetes.io/name=<your_application_name>` will be tracked by failure exporter.

```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: github-example-configuration
spec:
  exporters:
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
        extraEnv:
          - name: NAMESPACES
            value: <namespace_1,namespace_2>
      - app_name: committime-exporter
        exporter_type: committime
        extraEnv:
          - name: NAMESPACES
            value: <namespace_1,namespace_2>
          - name: TOKEN
            value: <github_token>
      - app_name: failure-exporter
        exporter_type: failure
        extraEnv:
          - name: PROVIDER
            value: github
          - name: TOKEN
            value: <github_token>
          - name: PROJECTS
            value: <github_repo_1,github_repo_2>
```
TEST WITH PRIVATE?
