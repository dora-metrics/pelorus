# Configuration

## Configuring Exporters

### Metrics Exporters (in development)

Before deploying, you must export your GITHUB_REPOS, GITHUB_USER and GITHUB_TOKEN to your shell. Then run:

    oc process -f templates/github-secret.yaml -p GITHUB_USER=${GITHUB_USER} -p GITHUB_TOKEN=${GITHUB_TOKEN} -p GITHUB_REPOS=${GITHUB_REPOS} | oc apply -f-
    oc process -f templates/exporter.yaml -p APP_NAME=commit-exporter | oc apply -f-
    
    
### Commit Time Exporter

The job of the commit time exporter is to find relevant builds in OpenShift and associate a commit from the build's source code repository with a container image built from that commit. We capture a timestamp for the commit, and the resulting image hash, so that the Deploy Time Exporter can later associate that image with a production deployment.

In order for proper collection, we require that all builds associated with a particular application be labelled with the same `application=<app_name>` label.

#### Deploying to OpenShift

Create a secret containing your GitHub token.

    oc create secret generic github-secret --from-literal=GITHUB_USER=<username> --from-literal=GITHUB_TOKEN=<personal access token> -n pelorus

Then deploy the chart.

    helm template charts/exporter/ -f exporters/committime/values.yaml --namespace pelorus | oc apply -f- -n pelorus

#### Running locally

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

#### Configuration

This exporter supports several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `APP_LABEL` | no | Changes the label key used to identify applications  | `application`  |
| `NAMESPACES` | no | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci` | unset; scans all namespaces |
| `GITHUB_USER` | yes | User's github username | unset |
| `GITHUB_TOKEN` | yes | User's Github API Token | unset |


### Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happen in a production environment.

In order for proper collection, we require that all deployments associated with a particular application be labelled with the same `application=<app_name>` label.

#### Deploying to OpenShift

Deploying to OpenShift is done via the exporter chart.

    helm template charts/exporter/ -f exporters/deploytime/values.yaml --namespace pelorus | oc apply -f- -n pelorus

#### Running locally

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
    
    
### Failure Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a failure occurs in a production environment and when it is resolved.

#### Deploying to OpenShift

Create a secret containing your Jira information.

    oc create secret generic jira-secret \
    --from-literal=SERVER=<Jira Server> \
    --from-literal=USER=<username> \
    --from-literal=TOKEN=<personal access token> \
    --from-literal=PROJECT=<Jira Project> \
    -n pelorus


Deploying to OpenShift is done via the failure exporter Helm chart.

**_NOTE:_** Be sure to update the appropiate values if `values.yaml` if necessary.

    helm template charts/exporter/ -f exporters/failure/values.yaml --namespace pelorus | oc apply -f- -n pelorus


#### Running locally

1. Install python deps:

        pip install -r requirements.txt [--user]

2. Export your Jira Information:

        SERVER=<Jira Server> 
        USER=<username> 
        TOKEN=<personal access token> 
        PROJECT=<Jira Project>

3. Then, you can simply run `app.py`

        python exporters/failure/app.py

If the exporter is working properly, you will see log lines like this indicating it has detected builds.

    Starting Failure Collector
    Starting Collection
    Found open issue: 2020-04-16T14:31:22.018-0400, MDT-1: Test issue for Feature #35
    Adding metric

You should also be able to hit the metrics endpoint and see our custom guages.

    $ curl localhost:8080/metrics/ | grep failure_timestamp

The cURL should return a similar result.

    # HELP failure_creation_timestamp Failure Creation Timestamp
    # TYPE failure_creation_timestamp gauge
    failure_creation_timestamp{issue_number="MDT-2",project="mdt"} 1.5875882e+09
    # HELP failure_resolution_timestamp Failure Resolution Timestamp
    # TYPE failure_resolution_timestamp gauge
    failure_resolution_timestamp{issue_number="MDT-2",project="mdt"} 1.587658112e+09
    # HELP failure_creation_timestamp Failure Creation Timestamp
    # TYPE failure_creation_timestamp gauge
    failure_creation_timestamp{issue_number="MDT-2",project="mdt"} 1.5875882e+09
    failure_creation_timestamp{issue_number="MDT-1",project="mdt"} 1.587061882e+09
    # HELP failure_resolution_timestamp Failure Resolution Timestamp
    # TYPE failure_resolution_timestamp gauge
    failure_resolution_timestamp{issue_number="MDT-2",project="mdt"} 1.587658112e+09
    failure_resolution_timestamp{issue_number="MDT-1",project="mdt"} 1.587575097e+09



#### Configuration

This exporter supports several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `SERVER` | yes | URL to the Jira Server  | unset  |
| `PROJECT` | yes | Jira project to scan | unset |
| `USER` | yes | Jira Username | unset |
| `TOKEN` | yes | User's API Token | unset |
