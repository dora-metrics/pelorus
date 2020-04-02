# Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

In order for proper collection, we require that all builds associated with a particular application be labelled with the same `application=<app_name>` label.

## Deploying to OpenShift

Create a secret containing your GitHub token.

    oc create secret generic github-secret --from-literal=GITHUB_USER=<username> --from-literal=GITHUB_TOKEN=<personal access token> -n pelorus

Then deploy the chart.

    helm template charts/exporter/ -f exporters/committime/values.yaml | oc apply -f- -n pelorus

## Running locally

1. Install python deps:

        pip install -r requirements.txt [--user]

2. Export your [Github API Credentials](https://github.com/settings/tokens):

        GITHUB_USER=<username>
        GITHUB_TOKEN=<personal access token>

3. Then, you can simply run `app.py`

        python exporters/committime/app.py

If the exporter is working properly, you will see log lines like this indicating it has detected builds.

    Namespace:  basic-nginx-build , App:  basic-nginx-02190cdc9fcf4bcc9562230b629b00f4519a4e81 , Build:  basic-nginx-1
    Namespace:  basic-nginx-build , App:  basic-nginx-02190cdc9fcf4bcc9562230b629b00f4519a4e81 , Build:  basic-nginx-2
    Namespace:  basic-spring-boot-build , App:  basic-spring-boot-360105605616ffc296a74e59ff82a6f25b6554d4 , Build:  basic-spring-boot-1
    Namespace:  basic-spring-boot-build , App:  basic-spring-boot-360105605616ffc296a74e59ff82a6f25b6554d4 , Build:  basic-spring-boot-2

You should also be able to hit the metrics endpoint and see our custom guages.

    $ curl localhost:8080/metrics/ | grep github_commit_timestamp

## Configuration

This exporter supports several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `APP_LABEL` | no | Changes the label key used to identify applications  | `application`  |
| `PROJECTS` | no | Restricts the set of projects from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all projects |
| `GITHUB_USER` | yes | User's github username | unset |
| `GITHUB_TOKEN` | yes | User's Github API Token | unset |