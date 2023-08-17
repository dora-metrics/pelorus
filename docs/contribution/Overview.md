# How to contribute to Pelorus

Here you can find how to contribute to Pelorus project and be part of the Pelorus community.

And remember: contributing includes much more than just writing code! Creating an issue, fixing a typo in the documentation or even telling people about Pelorus, already makes you part of the Pelorus community.

Thank you very much for your participation and contributing in the Pelorus community, your time and effort is highly appreciated!

## Spread the word

One very important thing that people usually forget about how to help a project grow and improve is divulgation. You can to this by

- talking about your Pelorus experience to friends and colleagues
- giving [Pelorus repository](https://github.com/dora-metrics/pelorus) a star
- watch [Pelorus repository](https://github.com/dora-metrics/pelorus) to know about new releases
<!-- slack channel (other social media) -->

## Issues/Questions

* To file a bug, please create a [Bug issue](https://github.com/dora-metrics/pelorus/issues/new?assignees=&labels=kind%2Fbug%2Cneeds-triage&template=bug.yml)

* To file a feature request, please create a [Request a new feature issue](https://github.com/dora-metrics/pelorus/issues/new?assignees=&labels=kind%2Ffeature%2Cneeds-triage&template=feature.yml)

* You may also consider opening a [discussion](https://github.com/dora-metrics/pelorus/discussions) thread to discuss any feature, bug, or enhancement prior to opening a Github issue.

## TODO CI/CD

## Integration in CI
Pelorus is being tested and it's parts such as container images or documentation are being created by various Continuous Integration systems.

Most of the CI runs are invoked using [Makefile](https://github.com/dora-metrics/pelorus/blob/master/Makefile) allowing developer to replicate those runs on the local computer. Please refer to the [Dev Guide](Development.md) for more information.

### GitHub Actions

Each Pull Request is being tested by various GitHub Actions corresponding to the files being modified or triggers such as new release. List of all GitHub Actions enabled for Pelorus can be found in the [.github](https://github.com/dora-metrics/pelorus/tree/master/.github) folder of the project.

### Prow OpenShift CI

Number of [Pelorus jobs](https://prow.ci.openshift.org/?job=*pelorus*) are running in dedicated Prow OpenShift CI, which is integrated with GitHub project. Triggers for those jobs are either new GitHub Pull Requests or periodic events.

Similarly to the [GitHub Actions](#github-actions) those jobs uses [Makefile](https://github.com/dora-metrics/pelorus/blob/master/Makefile) as the entry point for execution.

E2E Pull Request jobs consumes Pelorus deployment files, which are defined in the [mig-demo-apps values.yaml](https://github.com/konveyor/mig-demo-apps/blob/master/apps/todolist-mongo-go/pelorus/values.yaml) project and requires secrets that are configured using [vault.ci.openshift.org](https://vault.ci.openshift.org). Those secrets are then mounted by the [Prow job definition](https://github.com/openshift/release/blob/master/ci-operator/config/dora-metrics/pelorus/dora-metrics-pelorus-master__4.13.yaml#L127-L132) and used by the [Pelorus E2E script](https://github.com/dora-metrics/pelorus/blob/master/scripts/run-pelorus-e2e-tests.sh).

E2E periodic jobs uses deployment files defined in the [mig-demo-apps periodic folder](https://github.com/konveyor/mig-demo-apps/tree/master/apps/todolist-mongo-go/pelorus/periodic). Secrets and invocation script are identical to the Pull Request jobs differing in the [Makefile](https://github.com/dora-metrics/pelorus/blob/master/Makefile) targets, which uses different arguments passed to the [Pelorus E2E script](https://github.com/dora-metrics/pelorus/blob/master/scripts/run-pelorus-e2e-tests.sh).

Exporters list covered by the Prow CI is available in the [Backend Exporters](#backend-exporters) section.
