An **exporter** is a data collector application that pulls data from various tools and exposes it such that it can be consumed by Pelorus dashboards. Each exporter gets deployed individually alongside the core Pelorus stack.

There are currently three **exporter** types:

- [Deploy time](ExporterDeploytime.md)
- [Commit time](ExporterCommittime.md)
- [Failure](ExporterFailure.md)


Each exporter configuration option must be placed under `spec.exporters.instances` in the Pelorus configuration object YAML file as in the example:

```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: example-configuration
spec:
  [...] # Pelorus Core configuration options
  exporters:
    instances:
      [...] # Pelorus exporter configuration options
```

## Example

Configuration part of the Pelorus object YAML file, with some non-default options:

```yaml
kind: Pelorus
apiVersion: charts.pelorus.konveyor.io/v1alpha1
metadata:
  name: pelorus-instance
  namespace: pelorus
spec:
  [...] # Pelorus Core configuration options
  exporters:
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
        extraEnv:
          - name: NAMESPACES
            value: example_namespace
      - app_name: committime-exporter
        exporter_type: committime
        env_from_secrets:
        - bitbucket-secret
        extraEnv:
          - name: GIT_PROVIDER
            value: bitbucket
          - name: NAMESPACES
            value: example_namespace
      - app_name: failure-exporter
        exporter_type: failure
        env_from_secrets:
        - jira-secret
        env_from_configmaps:
        - jira-config
```

## List of all configuration options

This is the list of options that can be applied to `exporters.instances` section.

| Variable | Required | Default Value |
|----------|----------|---------------|
| [app_name](#app_name) | yes | - |
| [exporter_type](#exporter_type) | yes | - |
| [env_from_secrets](#env_from_secrets) | no | - |
| [env_from_configmaps](#env_from_configmaps) | no | - |
| [extraEnv](#extraenv) | no | - |
| [enabled](#enabled) | no | `true` |
| [custom_certs](#custom_certs) | no | - |
| [image_tag](#image_tag) | no | - |
| [image_name](#image_name) | no | - |
| [source_url](#source_url) | no | - |
| [source_ref](#source_ref) | no | - |

###### app_name

- **Required:** yes
- **Type:** string

: Set the exporter name.

###### exporter_type

- **Required:** yes
- **Type:** string

: Set the exporter type. One of `deploytime`, `committime`, `failure`.

###### env_from_secrets

- **Required:** no
- **Type:** list

: **Recommended for sensitive data**

: List of secrets, like in the following example.
```yaml
env_from_secrets:
- example-secret
- other-secret
```
**For more information, check [detailed Secrets examples](#secrets).**

: Check the list of all available options per exporter type:
: - [Deploy time](ExporterDeploytime.md#deploy-time-exporter-configuration-options)
- [Commit time](ExporterCommittime.md#commit-time-exporter-configuration-options)
- [Failure](ExporterFailure.md#failure-time-exporter-configuration-options)


###### env_from_configmaps

- **Required:** no
- **Type:** list

: List of ConfigMaps, like in the following example.
```yaml
env_from_configmaps:
- example-configmap
- other-configmap
```
**For more information, check [detailed ConfigMaps examples](#configmaps).**

: Check the list of all available options per exporter type:
: - [Deploy time](ExporterDeploytime.md#deploy-time-exporter-configuration-options)
- [Commit time](ExporterCommittime.md#commit-time-exporter-configuration-options)
- [Failure](ExporterFailure.md#failure-time-exporter-configuration-options)

###### extraEnv

- **Required:** no
- **Type:** list

: List of `name` and `value` pairs, like in the following example.
```yaml
extraEnv:
  - name: OPTION1
    value: value1
  - name: OPTION2
    value: value2
```

: Check the list of all available options per exporter type:
: - [Deploy time](ExporterDeploytime.md#deploy-time-exporter-configuration-options)
- [Commit time](ExporterCommittime.md#commit-time-exporter-configuration-options)
- [Failure](ExporterFailure.md#failure-time-exporter-configuration-options)

###### enabled

- **Required:** no
    - **Default Value:** true
- **Type:** boolean

: If set to `false`, the exporter is not deployed.

###### custom_certs

- **Required:** no
- **Type:** list

: List of `map_name`s, like in the following example.
```yaml
custom_certs:
  - map_name: name
```

: Check [Custom Certificates](#custom-certificates) for more information.

###### image_tag

- **Required:** no
    - Only applicable for development configuration, **do not use in production**
    - **Default Value:** stable
- **Type:** string

: Used to set exporter image tag (or custom image, if [image_name](#image_name) is set).

: Check [Development guide](../../Development.md) for more information.

###### image_name

- **Required:** no
    - Only applicable for development configuration, **do not use in production**
- **Type:** string

: Used to deploy exporter with the user built images or pre-built images hosted in non default container image registry. The container image URI may be with or without `:tag` suffix. If no tag suffix is specified in the URI, [image_tag](#image_tag) is used.

: Check [Development guide](../../Development.md) for more information.

###### source_url

- **Required:** no
    - Only applicable for development configuration, **do not use in production**
- **Type:** string

: Used to deploy exporter with the user Git source code.

: Check [Development guide](../../Development.md) for more information.

###### source_ref

- **Required:** no
    - Only applicable for development configuration, **do not use in production**
    - **Default Value:** points to the latest released Pelorus
- **Type:** string

: A Git reference or branch.

: Check [Development guide](../../Development.md) for more information.

## Examples

### Secrets

1. To create a Secret named **example-secret** in **pelorus** namespace, with the option **TOKEN** with value **token_value**, using the file **secret.yaml**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: example-secret
  namespace: pelorus
type: Opaque
stringData:
  TOKEN: "token_value"
```
run
```
oc apply -f secret.yaml
```
Then, add
```yaml
[...]
        env_from_secrets:
        - example-secret
[...]
```
to the exporter configuration. If no `metadata.namespace` is added to Secret file, you must run the command with the namespace you want to apply it. For example, `oc apply -f secret.yaml -n pelorus`. More [examples Secret files](https://github.com/konveyor/pelorus/tree/master/charts/secrets).

1. To create a secret named **other-secret** in **pelorus** namespace, with the

: - option **SERVER** with value **server_url**
: - option **API_USER** with value **username**
: - option **TOKEN** with value **token_value**

: run
```
oc create secret generic other-secret -n pelorus \
--from-literal=SERVER=server_url \
--from-literal=API_USER=username \
--from-literal=TOKEN=token_value
```
Then, add
```yaml
[...]
        env_from_secrets:
        - other-secret
[...]
```
to the exporter configuration.

### ConfigMaps

1. To create a ConfigMap named **example-config** in **pelorus** namespace, with the
: - option **APP_LABEL** with value **example**
: - option **NAMESPACES** with value **one,two**
: using the file **config.yaml**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: example-config
  namespace: pelorus
data:
  APP_LABEL: "example"
  NAMESPACES: "one,two"
```
run
```
oc apply -f config.yaml
```
Then, add
```yaml
[...]
        env_from_configmaps:
        - example-config
[...]
```
to the exporter configuration. If no `metadata.namespace` is added to ConfigMap file, you must run the command with the namespace you want to apply it. For example, `oc apply -f config.yaml -n pelorus`. More [examples ConfigMap files](https://github.com/konveyor/pelorus/tree/master/charts/configmaps).

1. To create a ConfigMap named **example-for-all** in **pelorus** namespace, that will be used by multiple exporters, with the option **LOG_LEVEL** with value **DEBUG**, using the file **config.yaml**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: example-for-all
  namespace: pelorus
data:
  LOG_LEVEL: "DEBUG"
```
run
```
oc apply -f config.yaml
```
Then, add
```yaml
[...]
        env_from_configmaps:
        - example-for-all
[...]
```
to each one of the exporters configuration.

## Authentication to Remote Services

Pelorus exporters make use of **personal access tokens** when authentication is
required.  It is recommended to configure the Pelorus exporters with authentication
via the **TOKEN** key to avoid connection rate limiting and access restrictions.

More information about some of the supported providers personal access tokens:

* [Github Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

* [Bitbucket Personal Access Tokens](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)

* [Gitea Tokens](https://docs.gitea.io/en-us/api-usage/#generating-and-listing-api-tokens)

* [Gitlab Personal Access Tokens](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)

* [Microsoft Azure DevOps Tokens](https://docs.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops&tabs=Windows)

To store a personal access token securely and to make it available to Pelorus, use OpenShift secrets. Pelorus can utilize secrets for all of the exporters. Check [env_from_secrets](#env_from_secrets) for examples.

## Custom Certificates

If you run services internally with certificates not signed by typical public root CAs,
you can supply your own custom certificates.

Currently, this is only supported for the following:

| Exporter Type | Provider |
|---------------|------------------|
| Commit Time   | GitHub           |
| Commit Time   | BitBucket        |
| Commit Time   | Gitea            |
| Commit Time   | GitLab           |
| Failure       | GitHub           |

We hope to expand this list in the future.

To use custom certificates, create ConfigMaps that have keys ending in `.pem`, with their values as PEM-formatted certificate files.

### Custom Certificates Example

First, you need a directory full of PEM-formatted certificates. Be careful not to expose private keys!

```console
$ ls ./certificates
trusted_internal_CA.pem
$ cat trusted_internal_CA.pem
-----BEGIN CERTIFICATE-----
(elided)
-----END CERTIFICATE-----
```

Next, create the ConfigMap named **my-certs** based on this directory.
```shell
oc create configmap my-certs --from-file=./certificates
```

Then, configure the exporter to use the ConfigMap's certificates:
```yaml
[...]
      - app_name: committime-exporter
        exporter_type: committime
        custom_certs:
          - map_name: my-certs
[...]
```

When it starts up, you should see information about custom certificate usage, depending upon your `LOG_LEVEL`:
```
08-24-2022 19:08:59 INFO Combining custom certificate file /etc/pelorus/custom_certs/my-certs/foo.pem
08-24-2022 19:08:59 DEBUG /opt/app-root/lib64/python3.9/site-packages/pelorus/certificates.py:48 _combine_certificates() Combined certificate bundle created at /tmp/custom-certsklkg4hel.pem
```

## Labels

Labels are key/value pairs that are attached to Kubernetes objects (pods, build configurations, etc), and providers objects (like issues, in the case of Issue Trackers providers).

Pelorus uses labels to identify objects that are relevant to it. The commit time, deploy time, and failure exporters all rely on labels to identify the application that is associated with it.

In Pelorus, the default label is **app.kubernetes.io/name=app_name**, where **app_name** is the name of one of the applications being monitored. The label can be customized by setting the `APP_LABEL` variable to your desired value, to give more context.

> **NOTE:** If labels are not properly set in the application objects and in the providers objects, Pelorus will not collect data from those.

### Examples

#### Application

In this example, an application named **todolist** is being monitored using the default label. So, all the application objects must have the `metadata.labels.app.kubernetes.io/name` YAML value set to **todolist**.

Example BuildConfig:
```yaml
- kind: BuildConfig
  apiVersion: build.openshift.io/v1
  metadata:
    name: todolist
    namespace: mongo-persistent
    labels:
      app.kubernetes.io/name: todolist
```

Example DeploymentConfig:
```yaml
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
```yaml
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

#### Failure exporter

In this example, we configure a Failure exporter to monitor issues from 2 GitHub Issue Trackers that:

* have **production_issue=app_name** label, where **app_name** is the name of one of the applications being monitored.

```yaml
[...]
      - app_name: failure-exporter
        exporter_type: failure
        env_from_secrets:
        - github-secret
        extraEnv:
          - name: PROJECTS
            value: konveyor/mig-demo-apps,konveyor/oadp-operator
          - name: APP_LABEL
            value: production_issue
[...]
```
