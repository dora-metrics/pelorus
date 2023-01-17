To deploy Pelorus to monitor your application(s), the following information are needed:

* The OpenShift Namespace(s) your application(s) is(are) deployed.
* The Git Provider(s) information (name, credentials, etc) your application(s) source code(s) is(are) hosted.
* The Issue Tracker(s) information (name, credentials, etc) your application(s) uses.

With this information gathered, Pelorus can be deployed following the steps.

![Pelorus Deployment Steps](../img/diagrams/pelorus_deployment_steps.png)

For more information on each step, check [Installation](Installation.md), [Core's Configuration](configuration/PelorusCore.md) and [Exporters' Configuration](configuration/PelorusExporters.md) documentation.
## Visualization

Pelorus is composed of Prometheus, Grafana and exporters. It can be easily deployed to an OpenShift cluster and provides an organizational-level view of critical measures.

![Pelorus Overview](../img/diagrams/pelorus_overview.png)

[:material-arrow-right: Further knowledge on Pelorus architecture](../Architecture.md)

## Terminology

- **Instance**: The set of Pelorus Core and Exporters objects.
- **Pelorus Core**: The storage manager.
- **Pelorus Exporter**: The metrics collector.
- **Provider**: The tools from where Pelorus Exporters collect the metrics.
- **Metric**: The data that is used to generate a measure.
- **Measure**: The outcome to make better decisions based on it.

## Supported Providers

List of providers supported by Pelorus.

### Deployment

<font size="5">

- OpenShift :simple-redhatopenshift:

</font>

### Git Providers

<font size="5">

- GitHub :simple-github:
- Bitbucket :simple-bitbucket:
- Gitea :simple-gitea:
- GitLab :simple-gitlab:
- Azure DevOps :simple-azuredevops:

</font>

### Issue Trackers

<font size="5">

- Jira :simple-jirasoftware:
- GitHub :simple-github:
- Service Now

</font>
