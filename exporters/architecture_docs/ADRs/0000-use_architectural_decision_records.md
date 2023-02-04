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

<dl>

<dt>Accepted</dt>
<dd>
The ADR has been accepted and merged.

However, this means "pending" if in a PR for a new ADR.

For example:
```markdown
## Status

Accepted
```
</dd>

<dt>Obsoleted</dt>
<dd>
The problem we try to solve is no longer relevant.

The reason why it is no longer relevant must be written below the status.

For example:
```markdown
## Status

Obsoleted

The $problem we needed to fix was fixed upstream,
so this approach is no longer necessary.
```
</dd>

<dt>Undecided</dt>
<dd>
The team was unable to come to a decision,
but we are keeping the ADR document for historical reference.
This is especially useful if the topic is revisited.

For example:
```markdown
## Status

Undecided

...

## Decision

Each approach has different tradeoffs.
We are keeping these notes because they are useful for historical reference.

We may revisit this after $feature exists in $tool, which makes the decision easier.
```
</dd>

</dl>

## Workflow

The ADR will be debated by stakeholders (see [the Debate section](#debate)).

If the ADR is accepted, the PR will be merged. If rejected, the PR will be closed.

PRs for minor changes (typo / format fixes) will not need to follow the whole process.

PRs may be opened to make ADRs easier to read.  
These PRs must not change the semantics of the ADR.  
They must have the same rigorous level of review, as if proposing a new ADR.  
However, the debate will not relitigate the ADR itself.  It is just to ensure consistency.

ADRs created retroactively, for decisions made before the process was adopted,
will not be debated for their _merits_, just for accuracy.

### Debate

These are deliberately not defined in this ADR, and will be discussed later:
- who are the stakeholders?
- what level of agreement do we need? (simple majority? unanimity? something else?)

## Rationale

The format draws from the best parts from the following sources, while trying to keep it simple:
- [Nygard's blog][nygard-blog]
- [the MADR format](https://adr.github.io/madr/)
- [What belongs in a successful PEP?](https://peps.python.org/pep-0001/#what-belongs-in-a-successful-pep)
- [the RFC format](https://www.ietf.org/blog/how-read-rfc/)

Underscores are easier to read, so they are used for the file title. It's also the norm in python, which the project is currently written in.

Rationale is separate so that the Decision is not cluttered.

## Alternatives Considered

These are implimentation alternatives. No alternatives to ADRs themselves have been proposed.

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

### Updating / Superceding ADRs

I had originally typed up a way to supercede / update ADRs a la RFCs,
but I think that falls under <abbr title="You Ain't Gonna Need It">YAGNI</abbr> (for now).

For future reference, I have kept [the original content of the status section in a gist](https://gist.github.com/KevinMGranger/15a421eda7a6f672c5a8ea11267e8c12).

## Addendum

Some of the wording in this ADR is inconsistent (imperative versus descriptive parts for the format), but that can be fixed in a cleanup PR later.

Although I tried to avoid pretending I'm an IETF member, I may have gone too far with some of the specification. Simplicity has its own strengths.


[nygard-blog]: https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions