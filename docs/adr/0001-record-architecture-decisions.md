# 1. Record architecture decisions

Date: 2023-03-08

## Status

Accepted

## Context

Use of ADR template and adr-tools-python project to record the Architecture Decision Records.

## Decision

Use of CLI tools and template provided by the [adr-tools-python](https://bitbucket.org/tinkerer_/adr-tools-python/) project to create and manage Architectural Decision Records for the Pelorus project.
    

## Consequences

To ensure proper documentation and communication, any design changes or functional enhancements to the Pelorus project should be recorded using an Architecture Decision Record (ADR) prior to merging pull request that implements such change.

The implementation pull request should depends on the ADR and be merged only after the ADR is approved and merged.

To create a new ADR or update an existing one, use the adr-new command-line interface (CLI) provided in the [adr-tools-python](https://bitbucket.org/tinkerer_/adr-tools-python/) project.

Please note that at the time of writing this ADR, it is not currently possible to replace the template provided by the adr-tools-python pip package, however, we may consider implementing such an update in the future.