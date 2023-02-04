# Architectural Decision Records (ADRs)

ADRs let us keep a record of the development choices we made,
the context of the problem, and why we picked the solution we did.

Our ADRs are kept in the [ADRs directory](./ADRs).

## Readings on ADRs
- [Michael Nygard's "Documenting architecture decisions"](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [Why you should be using architecture decision records to document your project (on redhat.com)](https://www.redhat.com/architect/architecture-decision-records)

## What goes in an ADR? (the short version)

> Number: A unique increasing number to help sort them from old to new
> Title: Indicates the content
> Context (Why): Describes the current situation and why you made this decision or thought it necessary—some variations explicitly break out an "alternatives covered" section to ensure all considerations get recorded
> Decision (What/How): Describes the what and how of the choice
> Status: Describes the status; note that ADRs can be superseded later by newer ADRs
> Consequences: Describes the effect of the decision, listing positive and negative aspects

## How do we propose a new ADR document?

Create a new file in the [ADRs directory](./ADRs) following the [agreed upon format](./ADRs/0000-use_architectural_decision_records.md).

Open a PR with it. Discuss in the PR.