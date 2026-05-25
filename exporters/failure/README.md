# Failure Time Exporter

The job of the failure exporter is to capture the timestamp at which a failure occurs in a production environment and when it is resolved.

```
# Creation
failure_creation_timestamp{app, issue_number} timestamp

# Resolution
failure_resolution_timestamp{app, issue_number} timestamp
```

Configuration options can be found in the [config guide](https://pelorus.readthedocs.io/en/latest/GettingStarted/configuration/ExporterFailure/)

## Supported Integrations

This exporter currently pulls failure data from the following systems:

* Jira
* Github
* ServiceNow
* PagerDuty
* Azure DevOps
