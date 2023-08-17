1. [Deployment Automation](#contributing-to-deployment-automation)
This track mostly involves testing, fixing, and updating our Helm chart(s) to streamline the installation and configuration experience. Knowledge of Helm, OpenShift, Operators and Prometheus configuration is assumed for this work.

## Contributing to Deployment Automation

We use [Helm](https://helm.sh) to provide an automated deployment and configuration experience for Pelorus. We are always doing work to cover more and more complex use cases with our helm charts. In order to be able to effectively contribute to these charts, you'll need a cluster that satisfies all of the installation prerequisites for Pelorus.

See the [Install guide](GettingStarted/Installation.md) for more details on that.

Currently we have 3 charts:

1. The [operators chart](https://github.com/dora-metrics/pelorus/blob/master/charts/operators/) installs the community operators on which Pelorus depends.
    * [Prometheus Operator](https://operatorhub.io/operator/prometheus)
    * [Grafana Operator](https://operatorhub.io/operator/grafana-operator)
2. The [pelorus chart](https://github.com/dora-metrics/pelorus/blob/master/charts/pelorus/) manages the Pelorus stack, which includes:
    * Thanos...
    * Prometheus rules etc...
    * A set of Grafana Dashboards and Datasources..
    * The Pelorus exporters, managed by the [exporter subchart](https://github.com/dora-metrics/pelorus/blob/master/charts/pelorus/charts/exporters).

We use Helm's [chart-testing](https://github.com/helm/chart-testing) tool to ensure quality and consistency in the chart. When making updates to one of the charts, ensure that the chart is valid using `make chart-check`. The most common linting failure is forgetting to bump the `version` field in the `Chart.yaml`. See below for instructions on updating the version.

### Updating the chart versions

When any of our Helm charts are updated, we need to bump their version. This allows for a seamless upgrade experience.

Check [Versioning Process](#versioning-process) section for more information.

### Helm Install changes

For testing changes to the helm chart, you should just follow the [standard install process](GettingStarted/Installation.md#helm-charts), then verify that:

* All expected pods are running and healthy
* Any expected behavior changes mentioned in the PR can be observed.

A different way is to simply run e2e-tests against your cluster. To do so, first export the necessary secrets to run the script, by running
```shell
export TOKEN=<YOUR_GITHUB_TOKEN>
export GITLAB_API_TOKEN=<YOUR_GITLAB_TOKEN>
export GITEA_API_TOKEN=<YOUR_GITEA_TOKEN>
export BITBUCKET_API_USER=<YOUR_BITBUCKET_USER>
export BITBUCKET_API_TOKEN=<YOUR_BITBUCKET_TOKEN>
export AZURE_DEVOPS_TOKEN=<YOUR_AZURE_DEVOPS_TOKEN>
export JIRA_USER=<YOUR_JIRA_USER>
export JIRA_TOKEN=<YOUR_JIRA_TOKEN>
export PAGER_DUTY_TOKEN=<YOUR_PAGER_DUTY_TOKEN>
```

Then, log in to your OpenShift cluster and **ENSURE** your pelorus namespace does not exist (if it exist, you can delete it running `oc delete namespace pelorus`), and run
```
make e2e-tests
```
which is an alias to `./scripts/run-pelorus-e2e-tests.sh -o konveyor -a -t`

To run e2e-tests from current branch, first create a PR in Pelorus project for it and export the necessary environment variables to run the script, by running
```shell
export REPO_NAME=pelorus
export PULL_NUMBER=<THE_PR_NUMBER>
```

For more information, run
```
./scripts/run-pelorus-e2e-tests.sh -h
```

To delete the objects created by the script, run
```
curl https://raw.githubusercontent.com/konveyor/mig-demo-apps/master/apps/todolist-mongo-go/mongo-persistent.yaml | oc delete -f -
helm uninstall pelorus --namespace pelorus
helm uninstall operators --namespace pelorus
```

You can do some rudimentary linting with `make chart-check`.

We are in the process of refactoring our helm charts such that they can be tested more automatically using [helm chart-testing](https://github.com/helm/chart-testing). Some general guidelines are outlined in the [CoP Helm testing strategy](https://redhat-cop.github.io/ci/linting-testing-helm-charts.html). More to come soon.


## Charts check

Every time you make a change to charts folder...

To check the validation and format of the project Helm charts (and all project versions), run
```
make chart-check
```
This will
- compare local Helm charts (and charts version) with the current Helm charts (and charts version) in [Pelorus repo](https://github.com/dora-metrics/pelorus) master branch (even if you are running it from your fork)
- run `ct lint` command, which uses
    - `scripts/config/ct.yaml` for [`ct`](https://github.com/helm/chart-testing) configuration
    - `scripts/config/chart_schema.yaml` for [`yamale`](https://github.com/23andMe/Yamale) configuration
    - `scripts/config/lintconf.yaml` for [`yamllint`](https://github.com/adrienverge/yamllint) configuration

This validation is enforced by the Project CI.
