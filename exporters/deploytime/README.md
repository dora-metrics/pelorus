# Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happens in a production environment.

```
deploy_timestamp{app, image_sha, namespace} timestamp
```

In order for proper collection, we require that all deployments associated with a particular application be labelled with a common label (`app.kubernetes.io/name` by default).

Configuration options can be found in the [config guide](https://pelorus.readthedocs.io/en/latest/GettingStarted/configuration/ExporterDeploytime/)

## Supported Integrations

This exporter currently pulls deployment data from the following systems:

* OpenShift - We look for `ReplicaSet` or `ReplicationController` resources where `.spec.template.spec.containers[*].image` contains a valid image SHA256 value. From there we grab:
  * `.spec.template.spec.containers[*].image`
  * `.metadata.creationTimestamp`
  * `.metadata.namespace`
  * `.metadata.labels.<application label>`