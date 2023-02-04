# Architecture Docs

This documentation covers the design decisions behind Pelorus's architecture and code.

For the choices we made architecturally, known as [Architecture Decision Records](https://www.redhat.com/architect/architecture-decision-records), see [ADRs.md](ADRs.md).

The [developer docs](https://pelorus.readthedocs.io/en/latest/Development/) are mainly about setting up a development environment, but we may move this in the future.

You may find docs for specific modules / packages in their respective folders.
For example, the [deserialization docs](../pelorus/deserialization/README.md) and [config loading docs](../pelorus/config/README.md).

# Common Libraries & Justification

## Attrs

We use attrs because it allows us to cut down on boilerplate,
and let us have easily correct dunder implementations (e.g. `__eq__`).

We use it instead of `dataclasses` because its converters and validators are useful to us.

## ExceptionGroup(s)

This backports `ExceptionGroup(s)` to our version of python.
They are the official way to collect parallel errors and present them,
which is one of the core features of our deserialization package.

## typing_extensions

The `typing` module gets better with every release of python.
This allows us to enjoy those improvements regardless of our version.