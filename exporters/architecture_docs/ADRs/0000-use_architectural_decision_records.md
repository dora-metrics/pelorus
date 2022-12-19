# Use Architectural Decision Records

# Status

Pending

## Context & Problem Statement

There are some choices we made in the past where we debated, weighed alternatives and tradeoffs, but didn't document our choices or why we chose them.
This means that newcomers to the project might not undertand why these choices happened.
But even longtime contributors can forget!

The benefits of ADRs have been outlined in [Michael Nygard's "Documenting architecture decisions"][nygard-blog]. There are additional references in [this Red Hat blog post about ADRs](https://www.redhat.com/architect/architecture-decision-records).

Stylistically, there are many formats to consider, each with different tradeoffs. How meta!

## Decision

We will use ADRs. 

Proposed ADRs will be written up in the below format, and opened as a Pull Request.

### The Format

The file name will be a unique increasing number that follows the nnnn-title_after_dash_with_underscores pattern.
(e.g. `0000-use_architectural_decision_records.md`)

To avoid merge conflicts, the `0000` should be kept as `NNNN` until the PR is accepted.

The file content sections will be:
- Title: indicate the content.
- Status: see [statuses](####statuses).
- Context & Problem Statement: describe the current situation, why this is necessary.
- Decision: the "what" and "how" of the decision.
- Rationale: the "why" of the decision.
- Alternatives Considered: if applicable. Includes why they were not chosen.
- For Future Discussion: if applicable. Includes the parts of the discussion that should be revisited later.
- Consequences: Describes the effect of the decision, listing positive and negative aspects. This _must_ be revisited later.

#### Statuses

The status will be put verbatim. Any additional requirements will be put below.

<dl>

<dt>Pending</dt>
<dd>Not yet accepted.</dd>

<dt>Accepted</dt>
<dd>Accepted and merged.</dd>

<dt>Obsoleted</dt>
<dd>
The problem we try to solve is no longer relevant.

The reason why it is no longer relevant must be written below the status.
</dd>

<dt>Superceded</dt>
<dd>
There is an ADR that supercedes this and all other updates to this ADR.  

That ADR must be linked below the status.
</dd>

<dt>Updated</dt>
<dd>
There are ADRs that update this one.

Those ADRs must be linked below the status.
</dd>

</dl>

If this ADR updates or supercedes another ADR, it must link to that ADR below the status.

## Workflow

If rejected, the PR will be closed without merging.

If accepted, the following will be updated:
- the status change(s) will be changed as applicable.
- the `NNNN` will be updated to the next sequential number.
- the PR will then be merged without waiting on CI checks.

PRs for non-substantial changes (typo / format fixes) will not need to follow the entire process.

PRs for clarity that don't change the semantics of the ADR must follow the process, but the debate is not for relitigating the ADR itself.
This is mainly for making it clearer to read after acceptance.

ADRs created retroactively, for decisions made before the process was adopted, do not need to be debated for their _merits_, just for accuracy.

## Rationale

The format draws from the best parts from the following sources, while trying to keep it simple:
- [Nygard's blog][nygard-blog]
- [the MADR format](https://adr.github.io/madr/)
- [the PEP format (What belongs in a successful PEP?)](https://peps.python.org/pep-0001/#what-belongs-in-a-successful-pep)
- [the RFC format](https://www.ietf.org/blog/how-read-rfc/)

## For Future Discussion

- Should the changes at acceptance time be automated, and if so, how?
- How do we decide on acceptance? Is it a majority vote? Must it be unanimous?



[nygard-blog]: https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions