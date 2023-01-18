# Configuration

## Configuring The Pelorus Stack

The Pelorus stack (Prometheus, Grafana, Thanos, etc.) can be configured by changing the `values.yaml` file that is passed to helm. The recommended practice is to make a copy of the one [values.yaml](https://github.com/konveyor/pelorus/blob/master/charts/pelorus/values.yaml) file and [charts/pelorus/configmaps/](https://github.com/konveyor/pelorus/blob/master/charts/pelorus/configmaps) directory, and store in your own configuration repo for safe keeping, and updating. Once established, you can make configuration changes by updating your `charts/pelorus/configmaps` files with `values.yaml` and applying the changes like so:

```
oc apply -f `myclusterconfigs/pelorus/configmaps
helm upgrade pelorus charts/pelorus --namespace pelorus --values myclusterconfigs/pelorus/values.yaml
```

The following configurations may be made through the `values.yaml` file:

| Variable                               | Required | Explanation                                                                                                                                                                                                                                                                                                                       | Default Value                          |
|----------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------|
| `openshift_prometheus_htpasswd_auth`   | yes      | The contents for the htpasswd file that Prometheus will use for basic authentication user.                                                                                                                                                                                                                                        | User: `internal`, Password: `changeme` |
| `openshift_prometheus_basic_auth_pass` | yes      | The password that grafana will use for its Prometheus datasource. Must match the above.                                                                                                                                                                                                                                           | `changme`                              |
| `custom_ca`                            | no       | Whether or not the cluster serves custom signed certificates for ingress (e.g. router certs). If `true` we will load the custom via the [certificate injection method](https://docs.openshift.com/container-platform/4.4/networking/configuring-a-custom-pki.html#certificate-injection-using-operators_configuring-a-custom-pki) | `false`                                |
| `exporters`                            | no       | Specified which exporters to install. See [Configuring Exporters](#configuring-exporters).                                                                                                                                                                                                                                        | Installs deploytime exporter only.     |

## Configuring Exporters Overview

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
### Authentication to Remote Services

Pelorus exporters make use of `personal access tokens` when authentication is
required.  It is recommended to configure the Pelorus exporters with authentication
via the `TOKEN` key to avoid connection rate limiting and access restrictions.

More information about personal access tokens:

* [Github Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

* [Jira / Bitbucket Personal Access Tokens](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)

* [Gitlab Personal Access Tokens](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)

* [Microsoft Azure DevOps Tokens](https://docs.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops&tabs=Windows)

* [Gitea Tokens](https://docs.gitea.io/en-us/api-usage/#generating-and-listing-api-tokens)

To store a personal access token securely and to make the token available to Pelorus use
Openshift secrets. Pelorus can utilize secrets for all of the exporters. The following
is an example for the committime exporter.

A simple Github example:
```shell
oc create secret generic github-secret --from-literal=TOKEN=<personal access token> -n pelorus
```

A Pelorus exporter can require additional information to collect data such as the 
remote `GIT_API` or `API_USER` information.  It is recommended to consult the requirements
for each Pelorus exporter in this guide and include the additional key / value information in the Openshift secret. An API example is `github.mycompany.com/api/v3`
or `https://gitea.mycompany.com`.

The cli commands can also be substituted with Secret templates. Example files can be found [here](https://github.com/konveyor/pelorus/tree/master/charts/pelorus/secrets)

Create a secret containing your Git username, token, and API example:

```shell
oc create secret generic github-secret --from-literal=API_USER=<username> --from-literal=TOKEN=<personal access token> --from-literal=GIT_API=<api> -n pelorus
```

A Jira example:
```shell
oc create secret generic jira-secret \
--from-literal=SERVER=<Jira Server> \
--from-literal=API_USER=<username/e-mail> \
--from-literal=TOKEN=<personal access token> \
-n pelorus
```

A ServiceNow example:
```shell
oc create secret generic snow-secret \
--from-literal=SERVER=<ServiceNow Server> \
--from-literal=API_USER=<username> \
--from-literal=TOKEN=<personal access token> \
--from-literal=TRACKER_PROVICER=servicenow \
--from-literal=APP_FIELD=<Custom app label field> \
-n pelorus
```

### Custom Certificates

If you run services internally with certificates not signed by typical public root CAs,
you can supply your own custom certificates.

Currently, this is only supported for the following exporters:

| Exporter Type | Exporter Backend |
|---------------|------------------|
| Commit Time   | BitBucket        |
| Commit Time   | Gitea            |
| Commit Time   | GitHub           |
| Commit Time   | GitLab           |
| Failure       | GitHub           |

We hope to expand this list in the future.

To use custom certificates, create `ConfigMap`s that have keys ending in `.pem`,
with their values as PEM-formatted certificate files.
Then under each exporter's `custom_certs` key, list each cert with `map_name: $NAME_HERE`. 

#### Custom Certificates Example

First, you need a dir full of PEM-formatted certificates. Be careful not to expose private keys!

```console
$ ls ./certificates
trusted_internal_CA.pem
$ cat trusted_internal_CA.pem
-----BEGIN CERTIFICATE-----
(elided)
-----END CERTIFICATE-----
```

Next, create the secret based on this directory.
```shell
oc create configmap my-certs --from-file=./certificates
```

Then configure the exporter to use the `ConfigMap`'s certificates:
```yaml
- app_name: committime-exporter
  exporter_type: committime
  custom_certs:
    - map_name: my-certs
```

When it starts up, you should see information about custom certificate usage, depending upon your `LOG_LEVEL`:
```log
08-24-2022 19:08:59 INFO Combining custom certificate file /etc/pelorus/custom_certs/my-certs/foo.pem
08-24-2022 19:08:59 DEBUG /opt/app-root/lib64/python3.9/site-packages/pelorus/certificates.py:48 _combine_certificates() Combined certificate bundle created at /tmp/custom-certsklkg4hel.pem
```

...and then requests to internal services using certs in the given chains should work.


### Labels

Labels are key/value pairs that are attached to Kubernetes objects (pods, build configurations, etc), and providers objects (like issues, in the case of Issue Trackers providers).

Pelorus uses labels to identify objects that are relevant to it. The commit time, deploy time, and failure exporters all rely on labels to identify the application that is associated with it.

In Pelorus, the default label is **app.kubernetes.io/name=app_name**, where **app_name** is the name of one of the applications being monitored. The label can be customized by setting the `APP_LABEL` variable to your desired value, to give more context.

> **NOTE:** If labels are not properly set in the application objects and in the providers objects, Pelorus will not collect data from those.

#### Examples

##### Application

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

##### Failure exporter

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

### Annotations and local build support

Commit Time Exporter may be used in conjunction with Builds **where values required to gather commit time from the source repository are missing**. In such case each Build is required to be annotated with two values allowing Commit Time Exporter to calculate metric from the Build.

To annotate Build use the following commands:

```shell
oc annotate build <build-name> -n <namespace> --overwrite io.openshift.build.commit.id=<commit_hash>

oc annotate build <build-name> -n <namespace> --overwrite io.openshift.build.source-location=<repo_uri>
```

Custom Annotation names may also be configured using Commit Time Exporter [ConfigMap Data Values](./ExporterCommittime.md#configmap-data-values).

Note: The requirement to label the build with `app.kubernetes.io/name=<app_name>` for the annotated Builds applies.

#### Example workflow for an OpenShift binary build

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

#### Additional Examples

There are many ways to build and deploy applications in OpenShift.  Additional examples of how to annotate builds such that Pelorus will properly discover the commit metadata can be found in the  [Pelorus tekton demo](https://github.com/konveyor/pelorus/tree/master/demo)

### Annotations, Docker Labels and Image support

Image object annotations similarly to [Annotations and local build support](#annotations-and-local-build-support) may be used for the Commit Time Exporter **where values from the Build objects required to gather commit time from the source repository are missing**.

Note: The requirement to label the image SHA with `app.kubernetes.io/name=<app_name>` for the annotated or Labeled Image objects applies.

Custom Annotation names may also be configured using Commit Time Exporter [ConfigMap Data Values](#configmap-data-values).

An Image object which is a result of Docker or Source-to-Image (S2I) builds set includes Docker Label `io.openshift.build.commit.date` metadata from which Commit Time Exporter gets the commit date. In such case Image object do not need to be annotated.

Example image metadata with `io.openshift.build.commit.date` Docker Labels and `app.kubernetes.io/name=<app_name>` Label required for the Commit Time Exporter:

```
IMAGE_SHA=588fb67a63ccbadf245b6d30747c404d809a851551b67c615a18217bf443a78e

$ oc describe image "sha256:${IMAGE_SHA}"

Docker Image:	image-registry.openshift-image-registry.svc:5000/mongo-persistent/todolist-mongo-go@sha256:588fb67a63ccbadf245b6d30747c404d809a851551b67c615a18217bf443a78e
Name:		    sha256:588fb67a63ccbadf245b6d30747c404d809a851551b67c615a18217bf443a78e
[...]
Labels:		    app.kubernetes.io/name=my-demo-application
[...]
Docker Labels:	io.buildah.version=1.22.4
		        io.openshift.build.commit.author=Wesley Hayutin <weshayutin@gmail.com>
		        io.openshift.build.commit.date=Mon Aug 8 13:13:58 2022 -0600
		        io.openshift.build.commit.id=b6abfb214557289bdaa9bed3dcc570ffd5b9ad4f
		        io.openshift.build.commit.message=Merge pull request #90 from mpryc/master
		        io.openshift.build.commit.ref=master
		        io.openshift.build.name=todolist-1
		        io.openshift.build.namespace=mongo-persistent
		        io.openshift.build.source-location=https://github.com/konveyor/mig-demo-apps.git
```

To annotate Image and ensure Commit Time Exporter can gather relevant values, use `oc annotate` CLI as in the following example:

```
$ NAME=my-application
$ IMAGE_SHA=588fb67a63ccbadf245b6d30747c404d809a851551b67c615a18217bf443a78e
$ oc label image "sha256:${IMAGE_SHA}" "app.kubernetes.io/name=${NAME}"

# In case image already has the `app.kubernetes.io/name` label, use --overwrite CLI option
$ oc label image "sha256:${IMAGE_SHA}" --overwrite "app.kubernetes.io/name=${NAME}"

> image.image.openshift.io/sha256:588fb67a63ccbadf245b6d30747c404d809a851551b67c615a18217bf443a78e labeled

$ oc annotate image "sha256:${IMAGE_SHA}" --overwrite \
     io.openshift.build.commit.date="Mon Aug 8 13:13:58 2022 -0600"

> image.image.openshift.io/sha256:588fb67a63ccbadf245b6d30747c404d809a851551b67c615a18217bf443a78e annotated

# It's not necessary for the Pelorus metric, but for completeness of the data, you may also annotate Git commit corresponding
# with the Image build:

$ oc annotate image "sha256:${IMAGE_SHA}" --overwrite \
    io.openshift.build.commit.id=b6abfb214557289bdaa9bed3dcc570ffd5b9ad4f \
    io.openshift.build.commit.date="Mon Aug 8 13:13:58 2022 -0600"

> image.image.openshift.io/sha256:588fb67a63ccbadf245b6d30747c404d809a851551b67c615a18217bf443a78e annotated
```

The Image may be also annotated with 10 digit EPOCH timestamp. Allowed format is one, where milliseconds are ignored:

```
$ EPOCH_TIMESTAMP=`git log -1 --format=%ct`
$ echo ${EPOCH_TIMESTAMP}
1663770655

$ NAME=my-application
$ IMAGE_SHA=588fb67a63ccbadf245b6d30747c404d809a851551b67c615a18217bf443a78e
$ oc label image "sha256:${IMAGE_SHA}" "app.kubernetes.io/name=${NAME}"

$ oc annotate image "sha256:${IMAGE_SHA}" --overwrite \
     io.openshift.build.commit.date="${EPOCH_TIMESTAMP}"
```
