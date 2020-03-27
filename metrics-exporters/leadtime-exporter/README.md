# Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

In order for proper collection, we require that all builds associated with a particular application be labelled with the same `application=<app_name>` label.

## Running locally

First you must export [Github API Credentials](https://github.com/settings/tokens):

    GITHUB_USER=<username>
    GITHUB_TOKEN=<personal access token>

Then, you can simply run `app.py`

    python metrics-exporters/leadtime-exporter/app.py