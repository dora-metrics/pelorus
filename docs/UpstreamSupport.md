# Pelorus Upstream Support Statement

The Pelorus engineering team will provide `best-effort` level support for Pelorus on the currently latest and the latest previous released versions of Openshift.  More specifically if the latest released version of Openshift is `4.11`, the engineering team will accept [issues](https://github.com/konveyor/pelorus/issues) written for OpenShift `4.11` and `4.10`.

* To file a bug please create a [Github issue](https://github.com/konveyor/pelorus/issues) with the label "kind/bug"

* To file a feature request create a [Github issue](https://github.com/konveyor/pelorus/issues) with the label "kind/feature"

* You may also consider opening a [discussion](https://github.com/konveyor/pelorus/discussions) thread to discuss any feature, bug, or enhancement prior to opening a Github issue.

## Backend Exporters

Pelorus's exporters support various backends or services. The Pelorus team is working to ensure an optimal experience for each backend integrated with Pelorus. Our goal is for each backend to be checked by OpenShift's Prow Continuous Integration system, to ensure the quality of each service's integration with Pelorus.

Below is a list of the status of each backend per Pelorus exporter. Any backend
with out CI integration will have an associated Github issue in CI status and Status.  To get the latest known status please refer to the issue.

### **Committime Exporter**

|Backend |Known issues        |CI status    |
|:--------|:--------------|:-------------|
| GitHub  | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-github)   | [Integration CI present](#integration-in-ci) |
| GitHub Enterprise | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-github-enterprise+) |  [todo](https://github.com/konveyor/pelorus/issues/561) |
| Bitbucket | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-bitbucket+) | [Integration CI present](#integration-in-ci) |
| Gitlab | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-gitlab) | [Integration CI present](#integration-in-ci) |
| Gitea | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-gitea) | [Integration CI present](#integration-in-ci) |
| Azure DevOps | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Acommittime-exporter+label%3Abackend-azure-devops) | [todo](https://github.com/konveyor/pelorus/issues/569) |

### **Failure Exporter**

|Backend |Known issues        |CI status    |
|:--------|:--------------|:-------------|
| Jira  | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Afailure-exporter+label%3Abackend-jira+ )   | [Integration CI present](#integration-in-ci) |
| GitHub  | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Afailure-exporter+label%3Abackend-github+)   | [Integration CI present](#integration-in-ci) |
| Service Now | [status link](https://github.com/konveyor/pelorus/issues?q=is%3Aopen+label%3Afailure-exporter+label%3Abackend-servicenow+) | [todo](https://github.com/konveyor/pelorus/issues/573) 

### **Deploytime Exporter**
|Backend |Known issues        |CI status    |
|:--------|:--------------|:-------------|
| OpenShift  | [status link](https://github.com/konveyor/pelorus/labels/deploytime-exporter)   | [Integration CI present](#integration-in-ci) |

## Integration in CI
Pelorus is being tested and it's parts such as container images or documentation are being created by various Continuous Integration systems.

Most of the CI runs are invoked using [Makefile](https://github.com/konveyor/pelorus/blob/master/Makefile) allowing developer to replicate those runs on the local computer. Please refer to the [Dev Guide](Development.md) for more information.

### GitHub Actions

Each Pull Request is being tested by various GitHub Actions corresponding to the files being modified or triggers such as new release. List of all GitHub Actions enabled for Pelorus can be found in the [.github](https://github.com/konveyor/pelorus/tree/master/.github) folder of the project.

### Prow OpenShift CI

Number of [Pelorus jobs](https://prow.ci.openshift.org/?job=*pelorus*) are running in dedicated Prow OpenShift CI, which is integrated with GitHub project. Triggers for those jobs are either new GitHub Pull Requests or periodic events.

Similarly to the [GitHub Actions](#github-actions) those jobs uses [Makefile](https://github.com/konveyor/pelorus/blob/master/Makefile) as the entry point for execution.

E2E Pull Request jobs consumes Pelorus deployment files, which are defined in the [mig-demo-apps values.yaml](https://github.com/konveyor/mig-demo-apps/blob/master/apps/todolist-mongo-go/pelorus/values.yaml) project and requires secrets that are configured using [vault.ci.openshift.org](https://vault.ci.openshift.org). Those secrets are then mounted by the [Prow job definition](https://github.com/openshift/release/blob/master/ci-operator/config/konveyor/pelorus/konveyor-pelorus-master__4.11.yaml#L122-L124) and used by the [Pelorus E2E script](https://github.com/konveyor/pelorus/blob/master/scripts/run-pelorus-e2e-tests).

E2E periodic jobs uses deployment files defined in the [mig-demo-apps periodic folder](https://github.com/konveyor/mig-demo-apps/tree/master/apps/todolist-mongo-go/pelorus/periodic). Secrets and invocation script are identical to the Pull Request jobs differing in the [Makefile](https://github.com/konveyor/pelorus/blob/master/Makefile) targets, which uses different arguments passed to the [Pelorus E2E script](https://github.com/konveyor/pelorus/blob/master/scripts/run-pelorus-e2e-tests).

Exporters list covered by the Prow CI is available in the [Backend Exporters](#backend-exporters) section.

## Thank you!

**Thank you very much for your participation in the Pelorus community, your time and effort is very much appreciated!**





