# Commit Time Exporter

The Commit Time exporter is responsible for collecting the following metric:

```
commit_timestamp{app, commit_hash, image_sha, namespace} timestamp
```

The job of the commit time exporter is to find relevant build data in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

In order for proper collection, we require that all builds associated with a particular application be labelled with a common label (`app.kubernetes.io/name` by default).

Configuration options can be found in the [config guide](/docs/Configuration.md)

## Supported Integrations

This exporter currently pulls build data from the following systems:

* OpenShift - We look for `Build` resources where `.spec.source.git.uri` and `.spec.revision.git.commit` are set. This includes:
  * Source to Image builds
  * Docker builds
  * JenkinsPipelineStrategy builds

* OpenShift - We look for `Build` resources with `Annotations` where `.spec.source.git.uri` and `.spec.revision.git.commit` were missing. This includes:
  * Binary (local) source build
  * Any build type

Then we get commit data from the following systems through their respective APIs:

* GitHub
* GitHub Enterprise (including private endpoints)
* Bitbucket _(coming soon)_
* Gitlab _(coming soon)_

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