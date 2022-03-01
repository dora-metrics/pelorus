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

## Binary Build Support

OpenShift binary builds are a popular mechanism for building container images on OenShift but do not contain source code information.

To support these types of build, you may annotate the build phase with the following annotations for pelorus to use:

| Annotation                      | Example                           | Description                   |
|---------------------------------|:----------------------------------|------------------------------:|
| buildSpecRevisionGitCommit      | cae392a                           | Short or Long Git Commit Hash |
| buildSpecSourceGitUri           | https://github.com/org/myapp.git  | URL of the Source Repository  |
| buildSpecRevisionGitAuthorName  | joe.bloggs                        | Name of the committer         |

Example command to put in your build pipeline each time you start an OpenShift `Build`:

```bash
oc annotate bc/${BUILD_CONFIG_NAME} --overwrite \
  buildSpecSourceGitUri=${GIT_URL} \
  buildSpecRevisionGitCommit=${GIT_COMMIT} \
  buildSpecRevisionGitAuthorName="${GIT_AUTHOR}"
```