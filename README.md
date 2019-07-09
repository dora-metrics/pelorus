# Metrics Driven Transformation Quickstart

Assets to rapidly demonstrate Metrics Driven Transformation (MDT) on the OpenShift Container Platform

## Prerequisites

* Ansible 2.7+
* OpenShift Environment
* OpenShift Command Line Tool
* [JQ](https://stedolan.github.io/jq/)
* [YQ](https://yq.readthedocs.io/en/latest/)

## Configuration

A bash script is used in combination with Ansible playbooks (some leveraging the [openshift-applier](https://github.com/redhat-cop/openshift-applier)) to build and provision the environment. The script makes use of several required parameters that must be provided either as environment variables or as script arguments.

The following table describes the various configuration options:

| Environment Variable | Command line Argument | Description | Default |
| -------------------- | --------------------- | ----------- | ------- |
| `OCP_SUBDOMAIN`      | `-s` or `--subdomain` | OpenShift default subdomain (ie: apps.openshift.example.com) |  |
| `GITHUB_TOKEN`       | `-g` or `--github-token` | GitHub client token |  |
| `JENKINS_NAMESPACE`  | `-j` or `--jenkins-namespace` | Project to deploy Jenkins | `basic-spring-boot-build` |
| `HYGIEIA_NAMESPACE`  | `-h` or `--namespace` | Project to deploy all other resources | `hygieia` |

## Provision

Execute the following command to provision the environment:

```
$ ./provision.sh -s=<subdomain> -g=<github_token>
```
