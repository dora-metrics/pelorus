# Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happen in a production environment.

In order for proper collection, we require that all deployments associated with a particular application be labelled with the same `application=<app_name>` label.

Configuration can be found in the [config guide](./docs/Configuration.md)
