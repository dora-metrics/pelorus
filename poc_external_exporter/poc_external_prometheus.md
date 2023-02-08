# Example of using Pelorus with external exporter

For more information, check [here](https://github.com/prometheus-operator/prometheus-operator/blob/main/Documentation/additional-scrape-config.md#creating-an-additional-configuration).

Create a file called `prometheus-additional.yaml`, with the following content
```yaml
- job_name: "test"
  static_configs:
  - targets: ["node.demo.do.prometheus.io"]
```
We could have added more than one target here and used any of this [configurations](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config).

Create Secret file from previous file
```
oc create secret generic additional-scrape-configs \
--from-file=prometheus-additional.yaml \
--dry-run=client -oyaml > additional-scrape-configs.yaml
```

Create Secret in the cluster
```
oc apply -f additional-scrape-configs.yaml -n pelorus
```

Create Pelorus instance with the following content
```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: github-example-configuration
spec:
  exporters:
    instances:
      - app_name: deploytime-exporter
        exporter_type: deploytime
        extraEnv:
          - name: NAMESPACES
            value: example_namespace
      - app_name: committime-exporter
        exporter_type: committime
        extraEnv:
          - name: NAMESPACES
            value: example_namespace
```

Navigate to Prometheus operator route and check the number of targets (in **Status** -> **Targets**). Tt should have 2 targets (1 deploytime and 1 committime).

Add the following content
```yaml
  additionalScrapeConfigs:
    name: additional-scrape-configs
    key: prometheus-additional.yaml
```
to the `spec` section of prometheus-pelorus yaml.

A **warning** message like
> **This resource is managed by github-example-configuration and any modifications may be overwritten. Edit the managing resource to preserve changes**

should appear. For this example, it can be ignored. Click on save.

To apply the changes, scale prometheus-prometheus-pelorus pods from 2 to 3 (it will return to 2 automatically). Navigate to Prometheus operator route again and check the number of targets. Tt should have 3 targets (1 deploytime and 1 committime and our test).
