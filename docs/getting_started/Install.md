# Installation

The following will walk through the deployment of Pelorus.

## Prerequisites

Before deploying Pelorus, the following tools are necessary

* A Unix machine from which to run the install (usually your laptop)
* An OpenShift 4.7 or higher environment
* [git](https://git-scm.com/)
* [oc](https://docs.openshift.com/container-platform/4.8/cli_reference/openshift_cli/getting-started-cli.html#installing-openshift-cli) The OpenShift CLI**\***
* [helm](https://helm.sh/) CLI 3 or higher**\***

>**Note:** It is possible to install `oc` and `helm` inside a Python virtual environment. To do so, change to Pelorus directory (after cloning its repository), and run
>```
>make dev-env
>source .venv/bin/activate
>```

## Initial Deployment

To begin, clone Pelorus repository. To do so, you can run
```
git clone https://github.com/konveyor/pelorus.git
```
which will download the latest code of Pelorus.

To download a stable version, run
```
git clone --depth 1 --branch <TAG> https://github.com/konveyor/pelorus.git
```
changing **TAG** by one of [Pelorus versions](https://github.com/konveyor/pelorus/tags).

Change the current directory to `pelorus`, by running
```
cd pelorus
```

Login to the OpenShift cluster as **kube:admin** (the specific user is really necessary?), by running
```
oc login
```

Create the namespace called `pelorus` that Pelorus will use, by running
```
oc create namespace pelorus
```
You can choose any name you wish, but remember to change to the same name in the following commands.

Pelorus gets installed via helm charts. First, deploy the operators on which Pelorus depends, by running
```
helm install operators charts/operators --namespace pelorus
```

Wait for the operators install to complete. (create script that checks when is finished https://github.com/hjwp/book-example/blob/master/functional_tests/base.py#L17 and I would change to an image)
```
$ oc get pods --namespace pelorus
NAME                                                   READY     STATUS    RESTARTS   AGE
grafana-operator-controller-manager-7678cc5c7c-spvls   2/2       Running   0          22s
prometheus-operator-559d659944-fvsjg                   1/1       Running   0          10s
```

Then, deploy the core Pelorus stack, by running
```
helm install pelorus charts/pelorus --namespace pelorus
```

Wait for the Pelorus install to complete.
```
$ oc get pods --namespace pelorus
NAME                                                   READY     STATUS      RESTARTS      AGE
deploytime-exporter-1-deploy                           0/1       Completed   0             93s
deploytime-exporter-1-rwk5l                            1/1       Running     0             90s
grafana-deployment-55f77ccc8f-d7m92                    2/2       Running     0             84s
grafana-operator-controller-manager-7678cc5c7c-spvls   2/2       Running     0             4m5s
prometheus-operator-559d659944-fvsjg                   1/1       Running     0             3m53s
prometheus-prometheus-pelorus-0                        3/3       Running     1 (89s ago)   93s
prometheus-prometheus-pelorus-1                        3/3       Running     1 (89s ago)   93s
```
(image is outdated!! deploy just completes but does not run?)

In a few seconds, you will see a number of resourced get created. The above commands will result in the following being deployed:

* Prometheus and Grafana operators
* The core Pelorus stack, which includes:
    * A `Prometheus` instance
    * A `Grafana` instance
    * A `ServiceMonitor` instance for scraping the Pelorus exporters.
    * A `GrafanaDatasource` pointing to Prometheus.
    * A set of `GrafanaDashboards`. See the [dashboards documentation](../Dashboards.md) for more details.
* The following exporters:
    * Deploy Time
    * Commit Time

To check this, run
```
oc get all --namespace pelorus
```
(hard to see, too  much information)

From here, some additional configuration is required in order to deploy other exporters. See the [Configuration Guide](../Configuration.md) for more information on exporters.

You may also want to enabled other features for the core stack. See the [Configuration2 Guide](configuration2.md) to understand those options.

To understand how to set up an application to Pelorus to watch, see [QuickStart tutorial](Demo.md).

To uninstall Pelorus, see the [Uninstall Guide](Uninstall.md).
