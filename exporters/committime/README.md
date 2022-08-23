# Commit Time Exporter

The Commit Time exporter is responsible for collecting the following metric:

```
commit_timestamp{app, commit_hash, image_sha, namespace} timestamp
```
The job of the commit time exporter is to find and associate time of the relevant source code commit with a container image SHA built from that source code. Later the Deploy Time Exporter can associate that image SHA with a production deployment and allow to calculate Lead Time for Change metrics.

In order for proper collection, we require that all builds associated with a particular application be labelled with a common label (`app.kubernetes.io/name` by default).

Configuration options can be found in the [config guide](/docs/Configuration.md)

## Supported Integrations

This exporter currently pulls commit data from the `Build` or an `Image` objects:

* OpenShift - We look for `Build` resources where `.spec.source.git.uri` and `.spec.revision.git.commit` are set. This includes:
  * Source to Image builds
  * Docker builds
  * JenkinsPipelineStrategy builds

* OpenShift - We look for `Build` resources with `Annotations` where `.spec.source.git.uri` and `.spec.revision.git.commit` were missing. This includes:
  * Binary (local) source build
  * Any build type

* OpenShift - We look for `Image` resources with `Docker Labels` or `Annotations`.

For the `Build` resources we get commit data from the following systems through their respective APIs:

* Azure DevOps
* Bitbucket
* Gitea
* GitHub
* GitHub Enterprise (including private endpoints)
* Gitlab

For the `Image` resources we get commit time from the:

* Value of an `io.openshift.build.commit.date` within the the `Docker Labels`
* Value of an `io.openshift.build.commit.date` within specified `COMMIT_DATE_ANNOTATION` env. variable, that defaults to `io.openshift.build.commit.date`

## Annotated Binary (local) source build support

OpenShift binary builds are a popular mechanism for building container images on OpenShift, where the source code is being streamed from a local file system to the builder.

These type of builds do not contain source code information, however you may annotate the build phase with the following annotations for pelorus to use:

| Annotation | Example | Description |
|:-|:-|:-|
| `io.openshift.build.commit.id` | cae392a | Short or Long hash of the source commit used in the build |
| `io.openshift.build.source-location` | https://github.com/org/myapp.git  | Source URL for the build |

Annotations for the hash and source-location may have different names. Configuration for such annotation is configurable via ConfigMap for the committime exporter. Example:

`COMMIT_HASH_ANNOTATION="io.custom.build.commit.id"`

`COMMIT_REPO_URL_ANNOTATION="io.custom.build.repo_url"`

Example command to put in your build pipeline each time you start an OpenShift `Build`:

```sh
oc annotate bc/${BUILD_CONFIG_NAME} --overwrite \
  io.openshift.build.commit.id=${GIT_COMMIT} \
  io.openshift.build.source-location=${GIT_URL} \
```
