# Pelorus Dashboards

TODO: Need some intro text

## Outcome: Software Delivery Performance

![Software Delivery Performance dashboard](/media/sdm-dashboard.png)

The _Software Delivery Performance_ dashboard measures the outcome of _Software Delivery Performance_. 

TODO

### Measures

Include visual showing relationship between exporters, metrics, pelorus, dashboard.

#### Lead Time for Change

TODO: Explain LTfC as a concept

Formula

##### Required Exporters

The following exporters are required to calculate _Lead Time for Change_:

* The [commit time exporter](/exporters/committime) provides the `commit_time` metric, which is the timestamp that a commit was made to source control.
* The [deploy time exporter](/exporters/deploytime) provides the `deploy_time` metric, which is a timestamp that a production deployment was rolled out.

The exporters are only responsible for gathering data about individual events. Before the dashboard consumes them, we perform some aggregation calculations in a set of [PrometheusRules](/charts/deploy/prometheus-rules.yaml). This converts individual `commit_time` and `deploy_time` data points into the following metrics:

* `sdp:lead_time:by_app` - Calculated lead times by application (`deploy_time - commit_time`)
* `sdp:lead_time:global` - A Global average of `sdp:lead_time:by_app`

The dashboard then displays these metrics over the given time ranges, and provides comparisons between the current and previous time range.

#### Deployment Frequency

TODO: Explanation

TODO: Formula

##### Required Exporters

The following exporters are required to calculate _Deployment Frequency_:

* The [deploy time exporter](/exporters/deploytime) provides the `deploy_time` metric, which is a timestamp that a production deployment was rolled out.

The dashboard then just tracks a `count_over_time()` of the individual `deploy_time` metrics for the time range selected in the dashboard. It also provides a comparison to the previous time range.

#### Mean Time to Restore

TODO: Explanation

TODO: Formula

##### Required Exporters

The following exporters are required to calculate _Mean Time to Restore_:

* The [failure exporter](/exporters/failure) provides the `failure_creation_timestamp` and `failure_resolution_timestamp` metrics, which attempt to capture the beginning and end of individual failure or degredation events in customer-facing systems. This data is typically collected from a ticketing system, though automated approaches of failure detection and tracking could be added in the future.

The exporters are only responsible for gathering data about individual events. Before the dashboard consumes them, we perform some aggregation calculations in a set of [PrometheusRules](/charts/deploy/prometheus-rules.yaml). This converts individual `failure_creation_timestamp` and `failure_resolution_timestamp` data points into the following metrics:

* `fr:time_to_restore` - A calculated time to restore for each failure event (`failure_resolution_timestamp - failure_creation_timestamp`)
* `fr:time_to_restore:global` - A global average of all `fr:time_to_restore` calculations.

The dashboard then displays this information for a given time range, and compares that number to the previous time range.

#### Change Failure Rate

TODO: Explanation

TODO: Formula

##### Required Exporters

The following exporters are require to calculate _Change Failure Rate_:

* The [failure exporter](/exporters/failure) provides the `failure_creation_timestamp` metrics, which attempt to capture the beginning of individual failure or degredation events in customer-facing systems. This data is typically collected from a ticketing system, though automated approaches of failure detection and tracking could be added in the future.
* The [deploy time exporter](/exporters/deploytime) provides the `deploy_time` metric, which is a timestamp that a production deployment was rolled out.

The exporters are only responsible for gathering data about individual events. Before the dashboard consumes them, we perform some aggregation calculations in a set of [PrometheusRules](/charts/deploy/prometheus-rules.yaml). This converts individual `failure_creation_timestamp` and `deploy_time` data points into the following metric:

* `fr:change_failure_rate` - A ratio of the number of failed changes to the total number of changes to the system.

The dashboard then displays this metric over the selected time range, as well as a compares it to the previous time range.