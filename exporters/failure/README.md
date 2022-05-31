# Failure Time Exporter

The job of the deploy time exporter is to capture the timestamp at which a failure occurs in a production environment and when it is resolved.

```
# Creation
failure_creation_timestamp{issue_number, project} timestamp

# Resolution
failure_resolution_timestamp{issue_number, project} timestamp
```

Configuration options can be found in the [config guide](/docs/Configuration.md)

## Supported Integrations

This exporter currently pulls build data from the following systems:

* Jira
* Github
* ServiceNow _(coming soon)_
