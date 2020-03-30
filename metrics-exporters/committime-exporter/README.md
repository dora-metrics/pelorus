# Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

In order for proper collection, we require that all builds associated with a particular application be labelled with the same `application=<app_name>` label.

## Running locally

1. Install python deps:

        pip install -r requirements.txt [--user]

2. Export your [Github API Credentials](https://github.com/settings/tokens):

        GITHUB_USER=<username>
        GITHUB_TOKEN=<personal access token>

3. Then, you can simply run `app.py`

        python metrics-exporters/leadtime-exporter/app.py

## Configuration

This exporter supports several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|---|
| `APP_LABEL` | no | Changes the label key used to identify applications  | `application`  |
| `PROJECTS` | no | Restricts the set of projects from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all projects |
| `GITHUB_USER` | yes | User's github username | unset |
| `GITHUB_TOKEN` | yes | User's Github API Token | unset |