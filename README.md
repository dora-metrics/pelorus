![Pelorus](docs/img/Logo-Pelorus-A-Standard-RGB_smaller.png)

[![Python Linting](https://github.com/dora-metrics/pelorus/actions/workflows/python-linting.yml/badge.svg)](https://github.com/dora-metrics/pelorus/actions)
[![Unit tests](https://github.com/dora-metrics/pelorus/actions/workflows/unittests.yml/badge.svg)](https://github.com/dora-metrics/pelorus/actions)
[![Conftest](https://github.com/dora-metrics/pelorus/actions/workflows/conftest.yml/badge.svg)](https://github.com/dora-metrics/pelorus/actions)
[![Chart Lint](https://github.com/dora-metrics/pelorus/actions/workflows/chart-lint.yml/badge.svg)](https://github.com/dora-metrics/pelorus/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Prow CI Periodic E2E Tests:

- OpenShift version 4.13 [![4.13 scenario 1 builds](https://prow.ci.openshift.org/badge.svg?jobs=periodic-ci-dora-metrics-pelorus-master-4.13-e2e-openshift-test-scenario-1-periodic)](https://prow.ci.openshift.org/job-history/gs/origin-ci-test/logs/periodic-ci-dora-metrics-pelorus-master-4.13-e2e-openshift-test-scenario-1-periodic)


Pelorus is a tool that helps IT organizations measure their impact on the overall performance of their organization. It does this by gathering metrics about team and organizational behaviors over time in some key areas of IT that have been shown to impact the value they deliver to the organization as a whole. Some of the key outcomes Pelorus can focus on are:

- Software Delivery Performance
- Product Quality and Sustainability
- Customer experience

For more background on the project you can read [@trevorquinn](https://github.com/trevorquinn)'s blog post on [Metrics Driven Transformation](https://www.openshift.com/blog/exploring-a-metrics-driven-approach-to-transformation).

## Software Delivery Performance as an outcome

Currently, Pelorus functionality can capture proven metrics that measure Software Delivery Performance -- a significant outcome that IT organizations aim to deliver.

Pelorus is a Grafana dashboard that can easily be deployed to an OpenShift cluster, and provides an organizational-level view of the [four critical measures of software delivery performance](https://blog.openshift.com/exploring-a-metrics-driven-approach-to-transformation/).

![Software Delivery Metrics Dashboard](docs/img/sdp-dashboard.png)

A short video describing each of these metrics is available [here](https://www.youtube.com/watch?v=7-iB_KhUaQg).

## Documentation

Pelorus documentation is available at [pelorus.readthedocs.io](https://pelorus.readthedocs.io/).

## Contributing to Pelorus

If you are interested in contributing to the Pelorus project, please review our Contribution guide which can be found in the [contribution guide](./CONTRIBUTING.md)

## Statement of Support

Our support policy can be found in the [Upstream Support statement](docs/UpstreamSupport.md)

## Code of Conduct
Refer to dora-metrics's Code of Conduct [here](./CODE_OF_CONDUCT.md).

## License

This repository is licensed under the terms of [Apache-2.0 License](LICENSE).
