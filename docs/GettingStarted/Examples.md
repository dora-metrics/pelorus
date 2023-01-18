In the following sections, we present example configurations for a variety of Git Providers and Issue Trackers combinations.

## Bitbucket & Jira

In this example, Pelorus will monitor only one application, where:

* The application:
    * is named **app_name** in OpenShift.
    * is deployed to the **example_namespace** Namespace in OpenShift.
* The application source code is hosted in Bitbucket.
    * Bitbucket user is **bitbucket_user**.
    * Bitbucket token is **bitbucket_token**.
* The application uses Jira as the Issue tracker. (Default)
    * Jira user is **jira_user**.
    * Jira token is **jira_token**.
    * Jira server is **example_server_url**.
    * Pelorus will only monitor issues:
        * of type **Bug**. (Default)
        * with priority **Hightest**. (Default)
        * labeled **example_label=app_name**.
    * Pelorus will monitor the issues in **example_project** project.
    * Pelorus will consider monitored issues to be resolved when their status change to **DONE**.

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
            value: example_namespace
      - app_name: committime-exporter
        exporter_type: committime
        extraEnv:
          - name: GIT_PROVIDER
            value: bitbucket
          - name: NAMESPACES
            value: example_namespace
          - name: API_USER
            value: bitbucket_user
          - name: TOKEN
            value: bitbucket_token
      - app_name: failure-exporter
        exporter_type: failure
        extraEnv:
          - name: API_USER
            value: jira_user
          - name: TOKEN
            value: jira_token
          - name: SERVER
            value: example_server_url
          - name: APP_LABEL
            value: example_label
          - name: PROJECTS
            value: example_project
          - name: JIRA_RESOLVED_STATUS
            value: DONE
```

To monitor more applications using Bitbucket & Jira as providers, we would have to:

* Add all the others namespaces (comma separated) in the `deploytime` exporter.
* Create a `committime` exporter for each application, like the previous one, but with their corresponding namespaces.
* Add all the others Jira projects (comma separated) in the `failure` exporter (or create new ones, if they live in different servers) and label issues properly with each application name.

## GitHub

In this example, Pelorus will monitor only one application, where:

* The application:
    * is named **app_name** in OpenShift.
    * is deployed to the **example_namespace** Namespace in OpenShift.
* The application source code is hosted in GitHub. (Default)
    * GitHub token is **github_token**.
* The application uses GitHub as the Issue tracker.
    * GitHub token is **github_token**.
    * Pelorus will only monitor issues labeled both with:
        * **bug**. (Default)
        * **example_label=app_name**.
    * Pelorus will monitor the issues in **user/example_repository** GitHub repository.
    * Pelorus will consider monitored issues to be resolved when they are closed.

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
            value: example_namespace
      - app_name: committime-exporter
        exporter_type: committime
        extraEnv:
          - name: NAMESPACES
            value: example_namespace
          - name: TOKEN
            value: github_token
      - app_name: failure-exporter
        exporter_type: failure
        extraEnv:
          - name: PROVIDER
            value: github
          - name: TOKEN
            value: github_token
          - name: APP_LABEL
            value: example_label
          - name: PROJECTS
            value: user/example_repository
```

To monitor more applications using GitHub as the provider, we would have to:

* Add all the others namespaces (comma separated) in the `deploytime` exporter.
* Create a `committime` exporter for each application, like the previous one, but with their corresponding namespaces.
* Create a `failure` exporter for each application, like the previous one, but with their corresponding GitHub repositories, and label issues properly with each application name.

## GitHub & Bitbucket & Jira

In this example, Pelorus will monitor two applications, where:

* The first application:
    * is named **app1** in OpenShift.
    * is deployed to the **namespace1** Namespace in OpenShift.
* The second application:
    * is named **app2** in OpenShift.
    * is deployed to the **namespace2** Namespace in OpenShift.
* The first application source code is hosted in GitHub. (Default)
    * GitHub token is **github_token**.
* The second application source code is hosted in Bitbucket.
    * Bitbucket user is **bitbucket_user**.
    * Bitbucket token is **bitbucket_token**.
* Both applications use Jira as the Issue tracker. (Default)
    * Jira user is **jira_user**.
    * Jira token is **jira_token**.
    * Jira server is **example_server_url**.
    * Pelorus will only monitor issues of type **Bug** and priority **Hightest**. (Default)
        * Issues labeled with **example_label=app1** are related to the first application.
        * Issues labeled with **example_label=app2** are related to the second application.
    * Pelorus will monitor the issues in **example_project** project.
    * Pelorus will consider monitored issues to be resolved when their status change to **DONE**.

```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: github-bitbucket-jira-example-configuration
spec:
  exporters:
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
        extraEnv:
          - name: NAMESPACES
            value: namespace1,namespace2
      - app_name: committime-exporter-app1
        exporter_type: committime
        extraEnv:
          - name: NAMESPACES
            value: namespace1
          - name: TOKEN
            value: github_token
      - app_name: committime-exporter-app2
        exporter_type: committime
        extraEnv:
          - name: GIT_PROVIDER
            value: bitbucket
          - name: NAMESPACES
            value: namespace2
          - name: API_USER
            value: bitbucket_user
          - name: TOKEN
            value: bitbucket_token
      - app_name: failure-exporter
        exporter_type: failure
        extraEnv:
          - name: API_USER
            value: jira_user
          - name: TOKEN
            value: jira_token
          - name: SERVER
            value: example_server_url
          - name: APP_LABEL
            value: example_label
          - name: PROJECTS
            value: example_project
          - name: JIRA_RESOLVED_STATUS
            value: DONE
```
