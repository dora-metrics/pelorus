# Troubleshooting

TODO add motivational/introduction text.

## Dashboards

### No data

If exporters are not functioning or deployed, no data will show up in the dashboards. It will look like the following image.

![No-Data](../img/pelorus-dashboard-no-data.png)

Please check the logs of exporter pod. (HOW???)

### Idle state

An "idle" state could resemble:

![Idle-Data](../img/pelorus-dashboard-idle-data.png)

(What to do in this case?)

## Raw data in the Pelorus Exporters logs

To get Pelorus committime exporter raw data, run
```
curl $(oc get route --namespace pelorus committime-exporter -o=template='http://{{.spec.host | printf "%s\n"}}')
```

To get Pelorus deploytime exporter raw data, run
```
curl $(oc get route --namespace pelorus deploytime-exporter -o=template='http://{{.spec.host | printf "%s\n"}}')
```
