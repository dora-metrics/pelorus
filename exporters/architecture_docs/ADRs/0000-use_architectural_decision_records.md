# Use Architectural Decision Records

# Status

Accepted

## Context & Problem Statement

There are some choices we made in the past where we debated, weighed alternatives and tradeoffs,
but we didn't document our choices or why we chose them.
This means that newcomers to the project might not undertand why these choices happened.
But even longtime contributors can forget!

The benefits of ADRs have been outlined in [Michael Nygard's "Documenting architecture decisions"][nygard-blog].
There are additional references in [this Red Hat blog post about ADRs](https://www.redhat.com/architect/architecture-decision-records).

Stylistically, there are many formats to consider, each with different tradeoffs. How meta!

## Decision

We will use ADRs. 

ADRs must be for important decisions regarding Pelorus's architecture, not to pretend we are IETF members.

Proposed ADRs will be written up in the below format, and opened as a Pull Request.

### The Format

We will use GitHub Flavored Markdown documents.

The final file name will be a unique sequential number that follows the `NNNN-title_after_dash_with_underscores` pattern.  
For example, `0000-use_architectural_decision_records.md`, which would be followed by `0001-some_other_adr.md`.  

The filename title may be a shorter version of the document title,
but they should try to remain consistent.

The file content sections will be as below.
The title will be an `h1` (`#`).

All other sections will be `h2`s (`##`) with their names verbatim,
as listed below before the colon.

Subsubsections (`h3` / `###` and lower) may be applied
as necessary, except for in the `Status` field.

- Title: indicate the content.
  - Notes to the reader may go below the title.
    Subsections may not be used here.
    These are for changing how one might interpret the below content (e.g. format changes).  
    This should be rare.
- Status: see [statuses](####statuses).
- Context & Problem Statement: describe the current situation; why this is necessary.
- Decision: the "what" and "how" of the decision.
- Rationale: the "why" of the decision. Can also be thought of as the context for the _decision_ more than the problem.
- Alternatives Considered: if applicable. Includes why they were not chosen.
- For Future Discussion: if applicable. Includes the parts of the discussion that should be revisited later. If these are revisited in a future ADR, that ADR should be linked here.
- Addendum: optional, additional, less-critical notes to the reader.
- Consequences: Describe the effect of the decision, listing positive and negative aspects. This _must_ be revisited later.


#### Statuses

The status will be put verbatim. Any additional requirements will be put below.

If an ADR relates to other ones in terms of status, for example:
- superceding
- updating
- having been superceded
- having been updated

...then those ADRs must be linked below the status, including their number and context. The context should be inspired by the name but need not be exact.

If an ADR's status changes, that context must be kept intact.
For specifics, see below.

Referenced ADRs should be crossed out if no longer relevant to the project.

<dl>

<dt>Accepted</dt>
<dd>
The ADR has been accepted and merged.

However, this means "pending" if in a PR for a new ADR.

If this ADR updates or supercedes another ADR, it must link to that ADR below the status.

For example:
```markdown
## Status

Accepted

Updates:
- [ADR 0004: Some ADR that left open questions (the one answered here)](0004-some_adr.md)
```
</dd>

<dt>Obsoleted</dt>
<dd>
The problem we try to solve is no longer relevant.

The reason why it is no longer relevant must be written below the status.

Any related ADRs should still be linked. If they are similarly
obsoleted, they should be crossed out.

For example:
```markdown
## Status

Obsoleted

The $problem we needed to fix was fixed upstream,
so this approach is no longer necessary.

Updates:
- ~~[ADR 0004: Some ADR that left open questions (the one answered here)](0004-some_adr.md)~~
- [ADR 0005: one that still applies](0005-still_applies.md)
```

</dd>

<dt>Updated</dt>
<dd>
There are ADRs that update this one.


An ADR is updated when there is another ADR that _adds_ to it,
substantially clarifies it, or lightly changes a small part of it.

For example:
```markdown
## Status

Updated

- by [ADR 0001: Stakeholders for ADRs and Agreement](0001-stakeholders_and_debate.md)
- by [ADR 0002: Changing The Format of $FOO](0002-$foo_format_change.md)
- ~~by [ADR 0003: one that got superceded](0003-got_superceded.md)~~
- by [ADR 0004: the one that superceded the above](0004-superceeds_0003.md)
```

If this ADR and its updates are completely _replaced_,
then this ADR is instead considered _superceded_.

</dd>

<dt>Superceded</dt>
<dd>
There is an ADR (or ADRs) that supercede this and all other updates to this ADR.

An ADR may be superceded by multiple when a problem / context is split into multiple ones.

Those ADRs must be linked below the status.

Any context to other ADRs should still be kept, but may be crossed out if also superceded.

An ADR is superceded when there is another ADR that "replaces" it.

For example:
```markdown
## Status

Superceded:
- by [ADR 0003: This Format Is Way Cooler](0003-cooler_format.md)
- by [ADR 0004: This other part is handled differently](0004-handled_differently.md)
```
</dd>


</dl>

## Workflow

The ADR will be debated by stakeholders (see [the Debate section](#debate)).

If the ADR is accepted, the PR will be merged. If rejected, the PR will be closed.

A PR for a new ADR that updates or supercedes other ADRs
must also update their statuses accordingly.


PRs for non-substantial changes (typo / format fixes) will not need to follow the entire agreement process.

PRs may be opened to make ADRs easier to read.  
These PRs will not change the semantics of the ADR.  
They must have the same rigorous level of review, as if proposing a new ADR.  
However, the debate will not relitigate the ADR itself.

ADRs created retroactively,
for decisions made before the process was adopted,
will not be debated for their _merits_, just for accuracy.

### Debate

The following points are deliberately not defined in this ADR,
and will be discussed later:
- who are the stakeholders
- what level of agreement we need (simple majority? unanimity? something else?)

## Rationale

The format draws from the best parts from the following sources, while trying to keep it simple:
- [Nygard's blog][nygard-blog]
- [the MADR format](https://adr.github.io/madr/)
- [What belongs in a successful PEP?](https://peps.python.org/pep-0001/#what-belongs-in-a-successful-pep)
- [the RFC format](https://www.ietf.org/blog/how-read-rfc/)

Underscores are easier to read, so they are used for the file title. It's also the norm in python, which the project is currently written in.

Rationale is separate so that the Decision is not cluttered.

## Alternatives Considered

### Use a generic NNNN number until accepted

While this helps avoid merge conflicts, this makes for additional work after acceptance.
We'd either need automation to make this change before merging, or make the change ourselves and skip CI, etc.
It also makes it harder to link to new ADRs that update / supercede other ADRs.

This workflow is simpler. Although there could be numeric conflicts, having multiple pending ADRs should be rare,
and resolving that conflict wouldn't be hard work.

### Have a `Pending` status until accepted

Although this is less confusing for those reading the ADR PR,
this creates additional work as mentioned above.

## For Future Discussion

[Debate definitions.](#debate)

If we think it's worth it, do we use automation to implement the alternatives mentioned above?

Where do we keep ADR docs?
Let's not bikeshed this, but note: they are related to developer and architecture docs, but are not really user facing.

## Addendum

Some of the wording in this ADR is inconsistent (imperative versus descriptive parts for the format), but that can be fixed in a cleanup PR later.

Although I tried to avoid pretending I'm an IETF member, I may have gone too far with some of the specification. Simplicity has its own strengths.


[nygard-blog]: https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions