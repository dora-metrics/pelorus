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

Then we get commit data from the following systems through their respective APIs:

* GitHub
* GitHub Enterprise (including private endpoints)
* Bitbucket _(coming soon)_
* Gitlab _(coming soon)_
