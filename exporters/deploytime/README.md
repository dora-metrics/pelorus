# Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happen in a production environment.

In order for proper collection, we require that all deployments associated with a particular application be labelled with the same `application=<app_name>` label.

## Deploying to OpenShift

Deploying to OpenShift is done via the exporter chart.

    helm template charts/exporter/ -f exporters/deploytime/values.yaml --namespace pelorus | oc apply -f-

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