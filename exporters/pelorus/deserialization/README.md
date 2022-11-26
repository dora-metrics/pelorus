# Motivation / Rationale

OpenShift / Kubernetes, by design, can't provide static guarantees
about API definitions. Although structure should be consistent by (resource)
version, this isn't enforced. Thus, most libraries only support dynamic typing.

Dynamic typing presents issues for type checking tools, which have been shown
to catch errors before they happen at runtime. While we can see and fix the
errors locally easily, seeing these errors on a user's cluster is hard.

The way of handling this before was to add debug statements and ask them to set
logging to the debug level. This has issues:

- the debug log statements clutter the code.
- debug logging also clutters the logs themselves. it's easy to miss information
  in the deluge of logs.
- we have to manually add logging for each field we look at.
- if errors are not handled per-field, accessing the field to log can still raise an Exception.
- handling errors per-field is incredibly verbose.
- falling back to a plain `except AttributeError` usually doesn't give enough information
- ...and misses `TypeError`s, `KeyError`s, etc.
- and bailing at the first error means we fix an issue or the user does, they run it again... only to encounter an issue with the next field we need.

We also deal with deeply nested fields a lot. We'd have to deal with errors at each level of nested access.
While the openshift library makes this convenient, it's at the cost of obtuse errors. `openshift_object.spec.revision.git.author.name` will just give
an `AttributeError: 'NoneType' object has no attribute author` if `git` is None... and if `name` is absent, we get `None` instead of an error. You get some context, but perhaps not enough.

And if developer tools want to help make this correct, you'd need
_six_ `if field is None` checks. And that's just for one field!

We need another solution for this.

# Goals

- Structure the data so it plays nicely with developer tools.
- Check _all_ fields before reporting an error.
- Make accessing nested data:
  - easy
  - less error-prone
  - report errors with better context
- Let the caller decide how to handle errors.
- Check that types are what we expect.
- Better distinguish data that is okay to be missing, and data that is required.

# Inspirations

## Functional Programming

In functional programming, there's this idea of `Result` and `Optional` types, which have some advantages:
- you have to handle the potential error before getting the succesful data (e.g. enforced `if value is None` checks).
- you can easily get a result object, but continue until you want to handle it (no exceptions making you end early.)
  - you can do this by wrapping each section in a `try` `except` but that's very verbose.

There are frameworks that let you compose parsing and validation functions,
taking advantage of these concepts.

## ExceptionGroups

Python developers have realized the usefulness of representing multiple errors at the same time.
In python 3.11, there are built-in Exception _Groups_ to support this.
3.11 even has new syntax to support this, not that we need it.

- [3.11 Release Notes: Exception Groups and except*](https://docs.python.org/3/whatsnew/3.11.html#whatsnew311-pep654)
- [PEP 654 – Exception Groups and except*](https://peps.python.org/pep-0654/)

# Implementation

We ask for source data and a target type to convert it to.
Depending upon the target type, we "dispatch" to different handlers for it.

Since these types can be arbitrarily nested, deserialization is recursive.
We keep a stack of "path" names, to keep track of where we are in the nested deserialization.
This data is used for error messages.

# Python `typing`

Generic types like `Union[str, None]` and `dict[str, int]` have two components:
the "origin" (`Union` and `dict`), and the arguments (`(str, None)` and `(str, int)`).

It's important to understand that `dict[str, int]` _is not a type_.
It will not work in `isinstance(x, dict[str, int])`.  However, `dict` _is_ a type.

# For the Future

From python 3.5 until python 3.10, there were two ways to express a value that can be a certain type or `None`.
`Untion[SomeType, None]`, or `Optional[SomeType]` (which is actually just an alias for the former!).

In python 3.10, you can express this as `SomeType | None`.
It's semantically the same, but is represented as a `types.UnionType`.
That will have to be added to our codebase for 3.10 support.