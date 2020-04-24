# Failure Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a failure occurs in a production environment and when it is resolved.

## Deploying to OpenShift

Create a secret containing your Jira information.

    oc create secret generic jira-secret \
    --from-literal=SERVER=<Jira Server> \
    --from-literal=USER=<username> \
    --from-literal=TOKEN=<personal access token> \
    --from-literal=PROJECT=<Jira Project> \
    -n pelorus


Deploying to OpenShift is done via the failure exporter Helm chart.

**_NOTE:_** Be sure to update the appropiate values if `values.yaml` if necessary.

    helm template charts/exporter/ -f exporters/failure/values.yaml --namespace pelorus | oc apply -f-


## Running locally

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



## Configuration

This exporter supports several configuration options, passed via environment variables

| Variable | Required | Explanation | Default Value |
|---|---|---|---|
| `SERVER` | yes | URL to the Jira Server  | unset  |
| `PROJECT` | yes | Jira project to scan | unset |
| `USER` | yes | Jira Username | unset |
| `TOKEN` | yes | User's API Token | unset |
