# Pelorus Tests

This directory contains selenium tests to verify that the dashboard is functioning correctly.

## Prerequisites

* An OpenShift 3.11 cluster with Pelorus installed
* The oc command line tool in the path.

## Running

First, you need to create a secret with a cluster login capable of viewing the dashboards.  Edit login.json with your credentials, then run:

```
oc create secret generic pelorus-test-login --from-file=login.json
```

Then run the run_test.sh script in this directory.  This will deploy a job to the cluster that will run the selenium tests.

## Creating tests

Tests should be named with the test_*.py convention and be placed in this directory.  The runner creates a configmap with the source code of any *.py file in this directory.  All py files starting with test_ are assumed by the framework to be tests.

The test harness utilizes python selenium with a headless chrome driver.  More information is available here https://selenium-python.readthedocs.io/