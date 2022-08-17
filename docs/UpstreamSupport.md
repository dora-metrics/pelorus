# Pelorus Upstream Support Statement

The Pelorus engineering team provides `best-effort` level support for Pelorus on the current and the most recent, previous versions of Openshift.  For example, if the latest released version of Openshift is `4.10`, the engineering team will accept [issues](https://github.com/konveyor/pelorus/issues) written for OpenShift `4.10` and `4.9`.

* To file a bug, create a [Github issue](https://github.com/konveyor/pelorus/issues) with the label "kind/bug".

* To request a feature, create a [Github issue](https://github.com/konveyor/pelorus/issues) with the label "feature".

* Consider opening a [discussion](https://github.com/konveyor/pelorus/discussions) thread to discuss any feature, bug, or enhancement prior to opening a Github issue.

## Backend Exporters
Pelorus exporters support various backends or services. The team is working to ensure an optimal experience for each backend integrated with Pelorus. Our goal is for each backend to be checked by OpenShift's Prow Continuous Integration system to ensure the quality of each service's integration with Pelorus.

Below is the status of each Pelorus backend exporter. Any backend without CI integration will have an associated Github issue in CI status and Status.  To get the latest known status please refer to the issue.

### Committime Exporter

|Backend |Status        |CI status    |
|:--------|:--------------|:-------------|
| GitHub  | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-github)   | Integration CI present|
| GitHub Enterprise | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-github-enterprise+) |  [todo](https://github.com/konveyor/pelorus/issues/561) |
| Bitbucket | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-bitbucket+) | [todo](https://github.com/konveyor/pelorus/issues/563) |
| Gitlab | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-gitlab) |  [todo](https://github.com/konveyor/pelorus/issues/565) |
| Gitea | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-gitea) | [todo](https://github.com/konveyor/pelorus/issues/567) |
| Azure DevOps | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-azure-devops) | [todo](https://github.com/konveyor/pelorus/issues/569) |

### Failure Exporter

|Backend |Status        |CI status    |
|:--------|:--------------|:-------------|
| Jira  | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Afailure-exporter+label%3Abackend-jira+ )   | [todo](https://github.com/konveyor/pelorus/issues/571) |
| GitHub  | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Afailure-exporter+label%3Abackend-github+)   | Integration  CI present|
| Service Now | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Afailure-exporter+label%3Abackend-servicenow+) | [todo](https://github.com/konveyor/pelorus/issues/573)

### Deploytime Exporter
|Backend |Status        |CI status    |
|:--------|:--------------|:-------------|
| OpenShift  | [status link](https://github.com/konveyor/pelorus/labels/deploytime-exporter)   | Integration CI present|


## Thank you!

**Thank you very much for your participation in the Pelorus community, your time and effort is very much appreciated!**
