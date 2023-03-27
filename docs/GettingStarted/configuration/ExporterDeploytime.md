# Deploy Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a deployment event happen in a production environment.

> **NOTE:** In order for proper collection, we require that all objects (Pods, Deployments, replicaSets, etc) associated with a particular application be labelled with the same [APP_LABEL](#app_label), which by default is `app.kubernetes.io/name=<app_name>`, where `<app_name>` is the name of the application being monitored.

## Example

Pelorus configuration object YAML file with three exporters, each typeof `deploytime`, and:

  - First exporter `deploytime-exporter1` monitors two namespaces `my-application1` and `my-application2` with the `DEBUG` log level.
  - Second exporter `deploytime-exporter2` monitors all namespaces that has the label `kubernetes.io/metadata.pelorus=monitored`.
  - Third exporter `deploytime-exporter3` monitors only the `mysql` namespace which contains an application created by the `oc new-app` command. Since all objects need proper label, it is important to run the command with `-l/--labels` flag. For example:
  ```
  oc new-app --image-stream=mysql:latest \
  -n mysql -e MYSQL_ROOT_PASSWORD=secret \
  -l app.kubernetes.io/name=mysql
  ```

```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: sample-pelorus-deployment
spec:
  exporters:
    instances:
      - app_name: deploytime-exporter1
        exporter_type: deploytime
        extraEnv:
          - name: LOG_LEVEL
            value: DEBUG
          - name: NAMESPACES
            value: my-application1,my-application2
      - app_name: deploytime-exporter2
        exporter_type: deploytime
        extraEnv:
          - name: PROD_LABEL
            value: kubernetes.io/metadata.pelorus=monitored
      - app_name: deploytime-exporter3
        exporter_type: deploytime
        extraEnv:
          - name: LOG_LEVEL
            value: DEBUG
          - name: NAMESPACES
            value: mysql
```

## Deploy Time Exporter configuration options

This is the list of options that can be applied to `env_from_secrets`, `env_from_configmaps` and `extraEnv` section of a Deploy time exporter.

| Variable | Required | Default Value |
|----------|----------|---------------|
| [LOG_LEVEL](#log_level) | no | `INFO` |
| [APP_LABEL](#app_label) | no | `app.kubernetes.io/name` |
| [NAMESPACES](#namespaces) | no | - |
| [PROD_LABEL](#prod_label) | no | - |
| [PELORUS_DEFAULT_KEYWORD](#pelorus_default_keyword) | no | `default` |

###### LOG_LEVEL

- **Required:** no
    - **Default Value:** INFO
- **Type:** string

: Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`.

###### APP_LABEL

- **Required:** no
    - **Default Value:** app.kubernetes.io/name
- **Type:** string

: Changes the label key used to identify applications.

###### NAMESPACES

- **Required:** no
    - **Default Value:** unset; scans all namespaces
- **Type:** comma separated list of strings

: Restricts the set of namespaces from which metrics will be collected.

###### PROD_LABEL

- **Required:** no
    - **Default Value:** unset; matches all namespaces
- **Type:** comma separated list of strings

: Changes the namespace label key used to identify namespaces that are considered production environments.
: **NOTE:** [PROD_LABEL](#prod_label) is ignored if [NAMESPACES](#namespaces) are provided

###### PELORUS_DEFAULT_KEYWORD

- **Required:** no
    - **Default Value:** default
- **Type:** string

: Used only when configuring instance using ConfigMap. It is the ConfigMap value that represents `default` value. If specified it's used in other data values to indicate "Default Value" should be used.
