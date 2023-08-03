# Pelorus Development Guide

We appreciate your interest in contributing to Pelorus! Use this guide to help you get up and running.

There are three main tracks of Pelorus development to consider. Any development changes that affect the design or introduce new functionality must be documented through an Architectural Design Record [submission](#how-to-propose-a-new-adr).

1. [Deployment Automation](#contributing-to-deployment-automation)
This track mostly involves testing, fixing, and updating our Helm chart(s) to streamline the installation and configuration experience. Knowledge of Helm, OpenShift, Operators and Prometheus configuration is assumed for this work.
2. [Dashboard Development](#dashboard-development)
This is where we take the raw data we've collected and turn it into actionable visual representations that will help IT organizations make important decisions. Knowledge of Grafana and PromQL is required for contribution here.
3. [Exporter Development](#exporter-development)
This track is focused around the development of custom [Prometheus exporters](https://prometheus.io/docs/instrumenting/writing_exporters/) to gather the information we need in order to calculate our core metrics. Python development experience is assumed.

## Architectural Decision Records

Architectural Decision Records (ADRs) let us keep a record of the development choices we made, the context of the problem, and why we picked the solution we did.

Our ADRs are kept in the [ADRs directory](https://github.com/dora-metrics/pelorus/tree/master/docs/adr/) following the [agreed upon format](./adr/0001-record-architecture-decisions.md).

### Readings on ADRs
- [Michael Nygard's "Documenting architecture decisions"](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [Why you should be using architecture decision records to document your project (on redhat.com)](https://www.redhat.com/architect/architecture-decision-records)

### ADR template

Our ADR template is sourced from the [adr-tools-python](https://bitbucket.org/tinkerer_/adr-tools-python/), and it comprises a few sections. `CAPITAL` words will be replaced by the tooling with generated values:

```markdown
# NUMBER. TITLE

Date: DATE

## Status

STATUS

## Context

The issue motivating this decision, and any context that influences or constrains the decision.
(Why): Describes the current situation and why you made this decision or thought it necessary—some variations explicitly break out an "alternatives covered" section to ensure all considerations get recorded.

## Decision

The change that we're proposing or have agreed to implement.
(What/How): Describes the what and how of the choice.

## Consequences

What becomes easier or more difficult to do and any risks introduced by the change that will need to be mitigated. List positive and negative aspects.
```

### How to propose a new ADR

Within the Pelorus GitHub fork directory:

1. Set up the dev environment

        make dev-env

2. Activate your virtual environment

        . .venv/bin/activate

3. Use the adr-new tool to create new ADR

        adr-new "Title of an ADR"

4. (Optional) If your new ADR is superseding an old ADR, use command as in the following example where `"My new ADR title"` is superseding ADR with number `0002`:

        adr-new -s 0002 "My new ADR title"

5. Modify newly created ADR file in the `docs/adr/` directory

6. Open a PR with it. Discuss in the PR.

7. Make the implementation PRs dependent on the ADRs PR

       To ensure the implementation's pull request is merged **after** the ADR's PR it is recommended to add `Depends on: #ADR_PULL_REQUEST_NUMBER` as the first comment on the implementation PRs. Please follow the [dpulls](https://www.dpulls.com/docs#/dependencies) for more information.

## Internal Architecture Docs

Documentation for low-level code architecture can be found in the
[architecture_docs directory](https://github.com/dora-metrics/pelorus/tree/master/architecture_docs).

Other components of the codebase may have their own architecture docs
in their respective folders.

## Python dependencies

The project uses [Poetry](https://python-poetry.org/) to manage the Python dependencies

### Add a Python dependency

To add a Python dependency, run
```
poetry add package_name
make update-requirements
```
This will add it to the required dependencies group. To add it to another group, use `-G` flag.

For more information, run `poetry add --help` or check [documentation](https://python-poetry.org/docs/cli/#add).

### Update a Python dependency

To update a Python dependency, run
```
poetry update package_name
make update-requirements
```

For more information, run `poetry update --help` or check [documentation](https://python-poetry.org/docs/cli/#update).

>**Note:** This should be CI responsibility.

### Remove a Python dependency

To remove a Python dependency, run
```
poetry remove package_name
make update-requirements
```

For more information, run `poetry remove --help` or check [documentation](https://python-poetry.org/docs/cli/#remove).

## Contributing to Deployment Automation

We use [Helm](https://helm.sh) to provide an automated deployment and configuration experience for Pelorus. We are always doing work to cover more and more complex use cases with our helm charts. In order to be able to effectively contribute to these charts, you'll need a cluster that satisfies all of the installation prerequisites for Pelorus.

See the [Install guide](GettingStarted/Installation.md) for more details on that.

Currently we have two charts:

1. The [operators](https://github.com/dora-metrics/pelorus/blob/master/charts/operators/) chart installs the community operators on which Pelorus depends.
    * [Prometheus Operator](https://operatorhub.io/operator/prometheus)
    * [Grafana Operator](https://operatorhub.io/operator/grafana-operator)
2. The [pelorus](https://github.com/dora-metrics/pelorus/blob/master/charts/pelorus/) chart manages the Pelorus stack, which includes:
    * Prometheus
    * Thanos
    * Grafana
    * A set of Grafana Dashboards and Datasources
    * The Pelorus exporters, managed in an [exporter](https://github.com/dora-metrics/pelorus/blob/master/charts/pelorus/charts/exporters) subchart.

We use Helm's [chart-testing](https://github.com/helm/chart-testing) tool to ensure quality and consistency in the chart. When making updates to one of the charts, ensure that the chart still passes lint testing using `make chart-lint`. The most common linting failure is forgetting to bump the `version` field in the `Chart.yaml`. See below for instructions on updating the version.

### Updating the chart versions

When any of our Helm charts are updated, we need to bump their version. This allows for a seamless upgrade experience.

Check [Versioning Process](#versioning-process) section for more information.

## Dashboard Development

We are continually doing work to enhance and bugfix the Pelorus dashboards. Doing so requires a complete Pelorus stack, including all exporters required to populate a given dashboard. See the [Outcomes (Dashboards)](philosophy/outcomes/Overview.md) user guide for that information.

To effectively do dashboard development, you'll likely need at least two browser windows open, one with Grafana, and another with Prometheus for testing queries. Since our dashboards are imported to Grafana via the Grafana Operator, they get imported in read-only mode. Because of this, you'll need to make a copy of it for development purposes.

The following outlines a workflow for working on a dashboard:

1. Sign in to Grafana via the Grafana route. To check the route:

        $ oc get route grafana-route -n pelorus

1. Once signed in, sign as an administrator
    1. Click the signin button in the bottom right corner:
    ![Signin button](img/signin.png)
    1. The admin credentials can be pulled from the following commands:

            $ oc get secrets -n pelorus grafana-admin-credentials -o jsonpath='{.data.GF_SECURITY_ADMIN_USER}' | base64 -d
            $ oc get secrets -n pelorus grafana-admin-credentials -o jsonpath='{.data.GF_SECURITY_ADMIN_PASSWORD}' | base64 -d
1. Export the dashboard JSON.
    1. Open the dashboard, and select the **Share...** button.
    1. Select the **Export** tab.
    1. Click **View JSON**.
    1. Click **Copy to Clipboard**.
1. Import as a new dashboard
    1. Click **Create** -> **Import**.
    1. Paste your JSON code in the box and click **Load**.
    1. Change the _Name_ and _Unique Identifier_ fields, and click **Import**.
1. Make changes to the live dashboard. You can do this by clicking the dropdown by the panel names, and selecting **Edit**.
1. Once you are happy with your changes, export your updated dashboard, and replace the existing content in the `GrafanaDashbaord` CR.
    1. Open the dashboard, and select the **Share...** button.
    1. Select the **Export** tab.
    1. Click **View JSON**.
    1. Click **Copy to Clipboard**.
    1. Open the appropriate `GrafanaDashboard` CR file, and paste the new dashboard JSON over the existing.

        **NOTE:**

        > Be sure to match the indentation of the previous dashboard JSON. Your git diffs should still show only the lines changed like the example below.

             $ git diff charts/deploy/templates/metrics-dashboard.yaml
             diff --git a/charts/deploy/templates/metrics-dashboard.yaml b/charts/deploy/templates/metrics-dashboard.yaml
             index 73151ad..c470afc 100644
             --- a/charts/deploy/templates/metrics-dashboard.yaml
             +++ b/charts/deploy/templates/metrics-dashboard.yaml
             @@ -25,7 +25,7 @@ spec:
                         "editable": true,
                         "gnetId": null,
                         "graphTooltip": 0,
             -            "id": 2,
             +            "id": 3,
                         "links": [],
                         "panels": [
                             {
             @@ -323,7 +323,7 @@ spec:
                             "tableColumn": "",
                             "targets": [
                                 {
             -                    "expr": "count (deploy_timestamp)",
             +                    "expr": "count (count_over_time (deploy_timestamp [$__range]) )",
                                 "format": "time_series",
                                 "instant": true,
                                 "intervalFactor": 1,
             @@ -410,7 +410,7 @@ spec:

You're done! Commit your changes and open a PR!

## Exporter Development

A Pelorus exporter is simply a [Prometheus exporter](https://prometheus.io/docs/instrumenting/writing_exporters/). While they can technically be written in many languages, we've written ours in Python using the [Prometheus python client](https://github.com/prometheus/client_python) library. We chose Python because it seems to be the most popular programming language for operations teams.

### Exporter directory layout

The following is a recommended directory structure for a Pelorus exporter `<NAME>`.

```
.
├── charts
│   └── pelorus
│       ├── configmaps
│       │   └── <NAME>.yaml
│       └── values.yaml
└── exporters
    ├── <NAME>
    │   ├── app.py
    │   └── README.md
    └── tests
        └── test_<NAME>.py
```

### Exporter installation sources

Each exporter can be deployed from the pre-built images or from the source code hosted in the accessible from the cluster GIT repository. Each exporter instance may be deployed using different method.

If not defined specifically, exporters are using pre-built container images with the `stable` tag from the following sources:

  * Quay repository for the [committime-exporter](https://quay.io/repository/pelorus/pelorus-committime-exporter)
  * Quay repository for the [failure-exporter](https://quay.io/repository/pelorus/pelorus-failure-exporter)
  * Quay repository for the [deploytime-exporter](https://quay.io/repository/pelorus/pelorus-deploytime-exporter)
  * Quay repository for the [releasetime-exporter](https://quay.io/repository/pelorus/pelorus-releasetime-exporter)
  * Quay repository for the [webhook-exporter](https://quay.io/repository/pelorus/pelorus-webhook-exporter)

#### Pre-built Quay images

Each pull request involving `exporters` folder that is merged results in new exporters images that are tagged with the commit hash (for example, `d6f6e6fa1c9d48ca1deeaf1c72585b94964cbf31` for the following [Pull Request](https://github.com/dora-metrics/pelorus/commit/d6f6e6fa1c9d48ca1deeaf1c72585b94964cbf31)) and with the exporters version (for example, `v2.0.10`). The newest images have the additional `latest` tag.

Each new Pelorus [release](https://github.com/dora-metrics/pelorus/releases) results in new exporters images that are tagged with all the previous tags and also `stable` tag.

These images are created using `exporters/Containerfile` file.

To build the image, in the `exporters` folder, run
```
podman image build --tag image:tag -f Containerfile .
```

To run the image, run
```
podman container run --rm -e APP_FILE=EXPORTER_TYPE/app.py image:tag
```

During Pelorus Helm deployment or update time, user have option to specify the image tag for each exporter instance individually. Example below shows two different tags for the commit time exporter and two tags for the failure exporter.

```yaml
exporters:
  instances:
  - app_name: webhook-exporter
    exporter_type: webhook
    image_type: latest

  - app_name: committime-github
    exporter_type: comittime
    image_tag: latest # Newest image from the last merged source code
    env_from_secrets:
    - github-credentials
    env_from_configmaps:
    - pelorus-config
    - committime-config

  - app_name: committime-gh-enterprise
    exporter_type: comittime
    image_tag: stable # By default it's `stable`, so we do not need to include image_tag here
    env_from_secrets:
    - github-enterprise-credentials
    env_from_configmaps:
    - pelorus-config
    - comittime-enterprise-config

  - app_name: failure-github
    exporter_type: deploytime
    image_tag: d6f6e6fa1c9d48ca1deeaf1c72585b94964cbf31 # Specific merge build
    env_from_secrets:
    - github-credentials
    env_from_configmaps:
    - pelorus-config
    - my-failure-github-config

  - app_name: jira-failure-exporter
    exporter_type: failure
    image_tag: v2.0.10 # Specific release
    env_from_secrets:
    - jira-credentials
    env_from_configmaps:
    - pelorus-config
    - my-failure-jira-config
```

#### Pre-built custom images

This method can be used to deploy Pelorus with the user built images or pre-built images mirrored in other than [quay.io](https://quay.io/) registry.

In such case the exporter instance configuration needs to include `image_name` that is in a format of full path to the image including image `:tag` or just image path without the `:tag` part. Not including image `:tag` results to use default `stable` tag unless `image_tag` configuration option is specified.

Example of such exporter instances are below:

```yaml
exporters:
  instances:
  - app_name: webhook-exporter
    exporter_type: webhook

  - app_name: committime-github
    exporter_type: comittime
    image_name: my.container.registry.io/pelorus/my-committime-exporter:latest # :stable would be used if no :latest was specified
    env_from_secrets:
    - github-credentials
    env_from_configmaps:
    - pelorus-config
    - committime-config

  - app_name: committime-gh-enterprise
    exporter_type: comittime
    image_name: my.container.registry.io/pelorus/my-committime-exporter # image tag specified in the image_tag line below
    image_tag: mytag
    env_from_secrets:
    - github-enterprise-credentials
    env_from_configmaps:
    - pelorus-config
    - comittime-enterprise-config
```

#### Image from source

By specifying `source_url` (and optionally `source_ref`), Pelorus exporters will use installation method that performs incremental builds of the exporter images using source from the GIT repository. Images are being stored in an OpenShift Container Platform registry and used during Pelorus deployment or update. Each instance that uses this method results in a new build. This method is recommended for development or unmerged bug-fixes as it may point to any GIT and any branch or GIT reference. By default `source_ref` points to master branch.

Example of such exporter instances are below:

```yaml
exporters:
  instances:
  - app_name: committime-github
    exporter_type: comittime
    source_url: https://github.com/dora-metrics/pelorus.git
    source_ref: refs/pull/567/head # References not merged GitHub pull request number 567
    env_from_secrets:
    - github-credentials
    env_from_configmaps:
    - pelorus-config
    - committime-config

  - app_name: committime-gh-enterprise
    exporter_type: comittime
    source_url: https://github.com/mypelorusfork/pelorus.git
    source_ref: testbranch # Use testbranch from mypelorusfork org
    env_from_secrets:
    - github-enterprise-credentials
    env_from_configmaps:
    - pelorus-config
    - comittime-enterprise-config
```

### Dev Environment Setup

#### Python & Repo Setup

After cloning the repo, you'll need a python version that's >= 3.9 but <= 3.11.

Running `make dev-env` should be enough to get you started.

This will:

- check for the right version of python
- set up a virtual environment
- install required CLI tools such as helm, oc, tkn and ct, promtool, conftest (inside .venv/bin)
- install required python runtime and test dependencies
- install the exporters package
- set up pre-commit hooks
- configure `git blame` to ignore large revisions that just changed formatting

##### Pre-commit

[pre-commit](https://pre-commit.com/) is configured automatically when running `make dev-env`.

To configure it manually, run
```shell
pre-commit install
```

To test it, run
```shell
pre-commit run --all-files
```

To bypass pre-commit checks, pass the `--no-verify` (`-n`) flag to `git commit` command.

pre-commit configuration in [`.pre-commit-config.yaml`](https://github.com/dora-metrics/pelorus/blob/master/.pre-commit-config.yaml) file.

#### IDE Setup (VSCode)

Most of us use Visual Studio Code to do our python development. The following extensions for VSCode are useful. Each can be installed by hitting `Ctrl+P` and pasting the commands below.

* [Markdown Preview Github Styling](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-preview-github-styles)

        ext install bierner.markdown-preview-github-styles

* [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)

        ext install ms-python.python

The python extension can activate your virtualenv automatically.

Code also comes with a nice debugger feature. Here is a starter configuration to use with our exporters. Just create a file called `.vscode/launch.json` in your `pelorus/` project directory with the following content.

```json
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Commit Time Exporter",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/exporters/committime/app.py",
            "console": "integratedTerminal",
            "env": {
                "API_USER": "<github username here>",
                "GITHUB_TOKEN": "<personal access token here>",
                "LOG_LEVEL": "INFO",
                "APP_LABEL": "app.kubernetes.io/name"
            }
        },
        {
            "name": "Deploy Time Exporter",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/exporters/deploytime/app.py",
            "console": "integratedTerminal",
            "env": {
                "LOG_LEVEL": "INFO",
                "APP_LABEL": "app.kubernetes.io/name"
            }        },
        {
            "name": "Deploy Time Exporter",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/exporters/failure/app.py",
            "console": "integratedTerminal",
            "env": {
                "SERVER": "<Jira server url>",
                "PROJECT": "<Jira project ID>",
                "API_USER": "<Jira username>",
                "TOKEN": "<Jira personal access token>",
                "LOG_LEVEL": "INFO",
                "APP_LABEL": "app.kubernetes.io/name"
            }
        }
    ]
}
```

For more information, see the [Debugging](https://code.visualstudio.com/docs/editor/debugging) doc in VS Code.

### Running locally

Running an exporter on your local machine should follow this process:

1. Set up your local dev environment:

        make dev-env

2. Activate your virtual environment

        . .venv/bin/activate

3. Set any environment variables required (or desired) for the given exporter (see [Configuring Exporters](GettingStarted/configuration/PelorusExporters.md) to see supported variables).

        export LOG_LEVEL=debug
        export TOKEN=xxxx
        export API_USER=xxxx

4. Log in to your OpenShift cluster  OR export KUBECONFIG environment variable

        oc login --token=<token> --server=https://api.cluster-my.fun.domain.com:6443

        # OR

        export KUBECONFIG=/path/to/kubeconfig_file

5. (Optional) To avoid certificate warnings and some possible errors, you need to set up your local machine to trust your cluster certificate

    1.  Download your cluster ca.crt file
    2.  Add cert to system trust bundle
    3.  Pass cert bundle with your login command

            oc login --token=<token> --server=https://api.cluster-my.fun.domain.com:6443  --certificate-authority=/etc/pki/tls/certs/ca-bundle.crt

6. Start the exporter

        python exporters/committime/app.py

At this point, your exporter should be available at http://localhost:8080

    curl http://localhost:8080/metrics

7. (Optional) Webhook exporter

Webhook type exporter has an additional URL target http://localhost:8080/pelorus/webhook, that allows to receive POST data, for example using curl:

    # Sample JSON payload files are in the exporters/tests/data directory
    $ cd exporters/tests/data/

    # JSON with payload (-d flag) must match the event type (-H "X-Pelorus-Event" flag):
    $ curl -X POST http://localhost:8080/pelorus/webhook -d @./webhook_pelorus_failure_created.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: failure"

## Operator Development

To create a new version (or pre-release) of Pelorus operator you must be logged into `podman` (`podman login` command) and then run
```
cd pelorus-operator
make podman-build
make bundle-build
make podman-push
make bundle-push
```
This will publish Pelorus operator images to [quay.io](https://quay.io/organization/pelorus).

To deploy it to OpenShift marketplace, a pull request must be created in [Openshift Community Operators repository](https://github.com/redhat-openshift-ecosystem/community-operators-prod). The Pelorus operator source code that is deployed to OpenShift marketplace is stored in [`operators/pelorus-operator/`](https://github.com/redhat-openshift-ecosystem/community-operators-prod/tree/main/operators/pelorus-operator) folder.

> The operator image and pull request creation are automated by the project CI. Check [Versioning Process](#versioning-process) section for more information

### API specification

Operator uses OpenAPI Specification under the rugs. This is useful when we want to add field validations, for example.

Helpful links for understanding Operator API specification:

- [https://swagger.io/docs/specification/about/](https://swagger.io/docs/specification/about/)
- [https://sdk.operatorframework.io/docs/olm-integration/generation/](https://sdk.operatorframework.io/docs/olm-integration/generation/)

### UI rendering

OpenShift allows custom UI rendering for Operator form view.

Helpful links for understanding OpenShift UI rendering:

- [https://github.com/openshift/console/blob/master/frontend/packages/operator-lifecycle-manager/src/components/descriptors/reference/reference.md](https://github.com/openshift/console/blob/master/frontend/packages/operator-lifecycle-manager/src/components/descriptors/reference/reference.md)
- [https://cloud.redhat.com/blog/openshift-4-2-declarative-dynamic-ui-for-your-operator](https://cloud.redhat.com/blog/openshift-4-2-declarative-dynamic-ui-for-your-operator)

### Testing

To test it out from image, run
```
operator-sdk run bundle quay.io/pelorus/pelorus-operator-bundle:<TAG> --namespace pelorus
```

To clean it up, run
```
operator-sdk cleanup pelorus-operator --namespace pelorus
```

During PRs, the CI builds a test image running
```sh
export REPOSITORY=quay.io/pelorus
export pr_type=opened
export pr_number=NUMBER
export commit_hash=HASH
cd exporters
docker image build --tag $REPOSITORY/rc-pelorus-exporter:vpr$pr_number-$commit_hash -f Containerfile .
docker push --all-tags $REPOSITORY/rc-pelorus-exporter
cd ..

cd pelorus-operator
export TEST_VERSION=pr$pr_number-$commit_hash
export CURRENT_OPERATOR_VERSION=$(grep "VERSION ?= " Makefile  | cut -c 12-)
export CURRENT_CHART_VERSION="$(grep '^version: ' helm-charts/pelorus/Chart.yaml  | cut -c 10-)"
export DEFAULT_OPERATOR_IMAGE=$REPOSITORY/pelorus-operator:$CURRENT_OPERATOR_VERSION
export TEST_OPERATOR_IMAGE=$REPOSITORY/rc-pelorus-operator:$TEST_VERSION
export DEFAULT_EXPORTER_IMAGE="$REPOSITORY/pelorus-{{ .exporter_type }}-exporter:{{ .image_tag | default \"v$CURRENT_CHART_VERSION\" }}"
export TEST_EXPORTER_IMAGE="$REPOSITORY/rc-pelorus-exporter:{{ .image_tag | default \"v$TEST_VERSION\" }}"

sed -i "s,$DEFAULT_OPERATOR_IMAGE,$TEST_OPERATOR_IMAGE,g" bundle/manifests/pelorus-operator.clusterserviceversion.yaml
sed -i "s,$DEFAULT_EXPORTER_IMAGE,$TEST_EXPORTER_IMAGE,g" helm-charts/pelorus/charts/exporters/templates/_imagestream_from_image.yaml
sed -i "s,$DEFAULT_EXPORTER_IMAGE,$TEST_EXPORTER_IMAGE,g" helm-charts/pelorus/charts/exporters/templates/_deploymentconfig.yaml
sed -i "s,$CURRENT_OPERATOR_VERSION,$TEST_VERSION,g" Makefile
sed -i "s,pelorus-operator,rc-pelorus-operator,g" Makefile
find . -type f | xargs sed -i "s,$CURRENT_OPERATOR_VERSION,$CURRENT_OPERATOR_VERSION-$TEST_VERSION,g"
find . -type f | xargs sed -i "s,$CURRENT_CHART_VERSION,$CURRENT_CHART_VERSION-$TEST_VERSION,g"

helm dep update helm-charts/pelorus
rm -r helm-charts/pelorus/charts/*.tgz

make podman-build
make bundle-build
make podman-push
make bundle-push
```
and comments on the PR how to use it.

## Testing Pull Requests

The following are notes and general steps for testing Pull Requests for specific types of changes.

To checkout PR we recommend using [GitHub CLI](https://cli.github.com/), which simplifies process of pulling PRs.

Ensure you have [Pelorus](https://github.com/dora-metrics/pelorus) GitHub project Forked into your GitHub user space.

#### <a id="checkout"></a>
Checkout the PR on top of your fork.

    git clone git@github.com:<your_github_username>/pelorus.git
    cd pelorus
    gh pr checkout 535

    # If asked:
    # ? Which should be the base repository, select:
    # > dora-metrics/pelorus


### Dashboard Changes

1. [Checkout](#checkout) the PR on top of your fork.

2. [Install Pelorus](GettingStarted/Installation.md) from checked out fork/branch.

    **NOTE:**

    > In most cases you can deploy changes to an existing deployment to retain existing data.

3. Log into Grafana via the grafana route.

        oc get route grafana-route -n pelorus

4. Click on the dashboard containing changes, and visually validate the behavior change described in the PR.

    **NOTE:**

    > Eventually we'd like to have some Selenium tests in place to validate dashboards. If you have skills in this area let us know!

### Exporter Changes

Each PR runs exporter tests in the CI systems, however those changes can be tested locally in a very similar way they run in the CI.

1. [Checkout](#checkout) the PR on top of your fork.

2. Set up the dev environment

        make dev-env

3. Activate your virtual environment

        . .venv/bin/activate

4. Check what type of tests you can run

        make help

5. As an example run unit tests using `make unit-tests`.

5. Gather necessary [configuration information](GettingStarted/configuration/PelorusExporters.md).
6. [Run exporter locally](#running-locally). You can do this either via the command line, or use the provided [VSCode debug confuration](#ide-setup-vscode) to run it in your IDE Debugger.
7. Once exporter is running, you can test it via a simple `curl localhost:8080`. You should be validating that:
    1. You get a valid response with metrics.
    1. Confirm the format of expected metrics.

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

You can do some rudimentary linting with `make chart-lint`.

We are in the process of refactoring our helm charts such that they can be tested more automatically using [helm chart-testing](https://github.com/helm/chart-testing). Some general guidelines are outlined in the [CoP Helm testing strategy](https://redhat-cop.github.io/ci/linting-testing-helm-charts.html). More to come soon.

## Versioning Process

Pelorus has the following versions

- [repository](https://github.com/dora-metrics/pelorus/releases)
- [exporters](https://quay.io/organization/pelorus)
- helm-charts
    - [pelorus (and exporters subchart)](https://github.com/dora-metrics/pelorus/blob/master/charts/pelorus/Chart.yaml)
    - [operators](https://github.com/dora-metrics/pelorus/blob/master/charts/operators/Chart.yaml)
- [operator](https://github.com/dora-metrics/pelorus/blob/master/pelorus-operator/bundle/manifests/pelorus-operator.clusterserviceversion.yaml#L511)

To simplify it, the repository, all exporters and all helm-charts versions are the same (which follow semantic versioning conventions) and each time one of them is bumped, the others are also bumped.

Pelorus versions should be bumped anytime a change to exporters code (`exporters` folder), or to helm-charts (`charts` folder) or even to operator code (`pelorus-operator` folder), is made. This is enforced by the project CI.

### Update during development version

After finishing a development change that modified any of the code that requires a version bump, run
```
./scripts/update_projects_version.py -f -r
```
to update the pre-release version.

### Create a release

To create a release on top of development changes, first create an issue for the release, using the [release issue template](https://github.com/dora-metrics/pelorus/issues/new?assignees=&labels=&projects=&template=release.yml&title=Release+of+Pelorus+Operator+version+%3CVERSION%3E).

Then, create a branch for the release you are about to make.

Then run the `update_projects_version` script using the `-l` (`--labels`) flag. It accepts one of the labels **major**, **minor** or **patch** for each of its 2 entries. The first entry is the chart version label and the second the operator version label.

**Examples:**

- To make a MINOR chart version and MAJOR operator version release, run
    ```
    ./scripts/update_projects_version.py -f -l minor major
    ```

- To make both chart version and operator version PATCH release, run
    ```
    ./scripts/update_projects_version.py -f -l patch patch
    ```

> A release pull request should only contain the changes from the script run

Create the pull request, using the [release template](https://github.com/dora-metrics/pelorus/blob/master/.github/PULL_REQUEST_TEMPLATE/release_template.md).

> If it is a minor or major chart release, ensure that the pull request is labeled with "minor" or "major" label.

After the pull request is merged, on the [Pelorus releases](https://github.com/dora-metrics/pelorus/releases) page, click edit on the latest **Draft** and click **Publish Release** to make a GitHub release.

To finish, review the PR opened by the CI in [community operators repository](https://github.com/redhat-openshift-ecosystem/community-operators-prod) and approve it to make the operator available in OpenShift marketplace.

## Testing the Docs

Our documentation gets published via [readthedocs](https://readthedocs.org/), via the [mkdocs](https://www.mkdocs.org/) framework. Mkdocs can be run locally for testing the rendering of the markdown files. If you followed the [local setup](#running-locally) instructions above, you should already have `mkdocs` installed.

Stand up the local server by running
```
mkdocs serve
```
To stop it, run `CTRL+C`.

If an error with `KeyError: 'Regular'` appears when testing the the documentation, run
```
rm -rf .cache && mkdocs serve
```
to fix it.

The mkdocs config is controlled by the `mkdocs.yml` file in the root of this project. All of the documents that will be served are in the [/docs](https://github.com/dora-metrics/pelorus/tree/master/docs) folder.

To generate diagrams images, run
```
(cd docs/img/diagrams && python generate_diagrams.py)
```
