# Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happen in a production environment.

In order for proper collection, we require that all deployments associated with a particular application be labelled with the same `app.kubernetes.io/name=<app_name>` label.

## Instance Config

```yaml
exporters:
  instances:
  - app_name: deploytime-exporter
    exporter_type: deploytime
    env_from_configmaps:
    - pelorus-config
    - deploytime-config
```

## ConfigMap Data Values

This exporter provides several configuration options, passed via `pelorus-config` and `deploytime-config` variables. User may define own ConfigMaps and pass to the committime exporter in a similar way.

| Variable                  | Required | Explanation                                                                                                       | Default Value                 |
|---------------------------|----------|-------------------------------------------------------------------------------------------------------------------|-------------------------------|
| `LOG_LEVEL`               | no       | Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`                                                     | `INFO`                        |
| `APP_LABEL`               | no       | Changes the label key used to identify applications                                                               | `app.kubernetes.io/name`      |
| `PROD_LABEL`              | no       | Changes the label key used to identify namespaces that are considered production environments.                    | unset; matches all namespaces |
| `NAMESPACES`              | no       | Restricts the set of namespaces from which metrics will be collected. ex: `myapp-ns-dev,otherapp-ci`              | unset; scans all namespaces   |
| `PELORUS_DEFAULT_KEYWORD` | no       | ConfigMap default keyword. If specified it's used in other data values to indicate "Default Value" should be used | `default`                     |
