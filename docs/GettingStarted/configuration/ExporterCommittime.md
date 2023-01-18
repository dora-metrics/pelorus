# Commit Time Exporter

The job of the commit time exporter is to find and associate time of the relevant source code commit with a container image SHA built from that source code.
Later the Deploy Time Exporter can associate that image SHA with a production deployment and allow to calculate [Lead Time for Change](../dashboards/SoftwareDeliveryPerformance/#lead-time-for-change) metrics.

Commit Time Exporter may be used with an Build or Image cluster objects.

## Using Commit Time with Git APIs

This is the default method of gathering commit time from the source code that triggered container build. Git commit hash and FQDN from the Build metadata are used to perform a query to a relevant Git API and collect commit time.

Currently we support GitHub, GitLab, BitBucket, Gitea and Azure DevOps Git services.

Open an [issue](https://github.com/konveyor/pelorus/issues/new) or a pull request to add support for additional Git providers!

We require that all builds associated with a particular application be labeled with the same `app.kubernetes.io/name=<app_name>` label. Different label name may be used with provided exporter instance configuration option `APP_LABEL`.

In some cases, such as binary build the `Build` object may be missing information required to gather Git commit time. Refer to the [Annotations and local build support](#annotations-and-local-build-support) for information how to enable Commit Time Exporter for such builds.

### Instance Config

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

## Using Commit Time with Images

This is the method of gathering source commit time associated directly with an `Image` object, where `Build` object may be missing.

To configure Commit Time Exporter with an `image` provider type, ensure ConfigMap has such option and it's used in the committime instance config, similarly to the example:

ConfigMap file:

```
kind: ConfigMap
metadata:
  name: image-committime-config
  namespace: pelorus
data:
  PROVIDER: "image"
```

Instance Config:

```yaml
exporters:
  instances:
  - app_name: image-committime-exporter
    exporter_type: committime
    env_from_configmaps:
    - pelorus-config
    - image-committime-config
```
Refer to the [Annotations, Docker Labels and Image support](#annotations-docker-labels-and-image-support) for information how to enable Commit Time Exporter for the Image use case.

## ConfigMap Data Values

This exporter provides several configuration options, passed via `pelorus-config` and `committime-config` variables. User may define own ConfigMaps and pass to the committime exporter in a similar way.

| Variable                     | Required | Supported provider | Explanation                                                                                                                                                              | Default Value                                                             |
|------------------------------|----------|--------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| `PROVIDER`                   | no       |                    | Provider from which commit date is taken. `git` or `image`                                                                                                               |                                                                           |
| `API_USER`                   | yes      | `git`              | User's github username                                                                                                                                                   | unset                                                                     |
| `TOKEN`                      | yes      | `git`              | User's Github API Token                                                                                                                                                  | unset                                                                     |
| `GIT_API`                    | no       | `git`              | GitHub, Gitea or Azure DevOps API FQDN. This allows the override for Enterprise users. Currently only applicable to `github`, `gitea` and `azure-devops` provider types. | `api.github.com`, or `https://try.gitea.io`. No default for Azure DevOps. |
| `GIT_PROVIDER`               | no       | `git`              | Set Git provider type. Can be `github`, `bitbucket`, `gitea`, `azure-devops` or `gitlab`                                                                                 | `github`                                                                  |
| `LOG_LEVEL`                  | no       | `git`, `image`     | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`                                                                                                            | `INFO`                                                                    |
| `APP_LABEL`                  | no       | `git`, `image`     | Changes the label key used to identify applications                                                                                                                      | `app.kubernetes.io/name`                                                  |
| `NAMESPACES`                 | no       | `git`              | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci`                                                                     | unset; scans all namespaces                                               |
| `PELORUS_DEFAULT_KEYWORD`    | no       | `git`, `image`     | ConfigMap default keyword. If specified it's used in other data values to indicate "Default Value" should be used                                                        | `default`                                                                 |
| `COMMIT_HASH_ANNOTATION`     | no       | `git`, `image`     | Annotation name associated with the Build from which hash is used to calculate commit time                                                                               | `io.openshift.build.commit.id`                                            |
| `COMMIT_REPO_URL_ANNOTATION` | no       | `git`, `image`     | Annotation name associated with the Build from which GIT repository URL is used to calculate commit time                                                                 | `io.openshift.build.source-location`                                      |
| `COMMIT_DATE_ANNOTATION`     | no       | `image`            | Annotation name associated with the Image from which commit time is taken.                                                                                               | `io.openshift.build.commit.date`                                          |
| `COMMIT_DATE_FORMAT`         | no       | `image`            | Format in `1989 C standard` to convert time and date found in the Docker Label `io.openshift.build.commit.date` or annotation for the Image                              | `%a %b %d %H:%M:%S %Y %z`                                                 |
