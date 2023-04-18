# 3. End to end tests

Date: 2023-04-18

## Status

Accepted

## Context

End to end (e2e) tests only run tests against exporters `/metrics` endpoint in OpenShift today (using Prow CI). We want to run them with more cases, like against Grafana, making them more reliable.

## Decision

e2e tests will be more user friendly.

Prow CI will run e2e tests that cover more scenarios and are more reliable.

### How

- We will rewrite the e2e tests script in Python.
    - easier to write and read it
    - they will run against Pelorus operator (using test image) and not helm

- We will write better documentation on what e2e tests do (script help and read the docs).
    - more accessible to new developers of the Pelorus project

- We will log only relevant information on tests run.
    - Too much log information is not good to identify a simple error

- We will not use `mig-demo-apps` anymore.
    - make development faster (only one PR and everything in one repository)
    - do not use yaml files for different tests scenarios
        - use `image_name` option instead of `source_url` for faster runs (using test image)
    - use the simplest application possible for tests (faster tests runs)

- New commits/deployments/issues will be created for each test scenario.
    - To address new approach of Pelorus metrics

- We will have more tests scenarios:
    - check each exporter `/metrics` endpoint
    - check Grafana dashboards for each application
    - webhook exporter tests

## Consequences

### Pros

- Faster and more reliable tests (some tests were manual)
- Faster runs (using a simpler application)
- Individual runs (`todolist` application for GitHub was always run)
- Faster development
- Easier to identify errors

### Cons

- Create new commits/issues to providers in each run, which should be cleaned afterwards (more complexity)
