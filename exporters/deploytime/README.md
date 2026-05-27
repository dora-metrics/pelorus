# Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happens in a production environment.

```
deploy_timestamp{app, image_sha, namespace} timestamp
```

In order for proper collection, we require that all deployments associated with a particular application be labelled with a common label (`app.kubernetes.io/name` by default).

Configuration options can be found in the [config guide](https://pelorus.readthedocs.io/en/latest/GettingStarted/configuration/ExporterDeploytime/)

## Supported Integrations

This exporter currently pulls deployment data from the following systems:

* OpenShift/Kubernetes - We find running `Pod` resources owned by a `ReplicaSet` or `ReplicationController` and matching the configured app label. For each unique owner we grab:
  * Image SHA256 from `pod.status.containerStatuses[*].imageID`
  * `creationTimestamp` from the owner `ReplicaSet`/`ReplicationController`
  * `namespace` and app label from the `Pod`