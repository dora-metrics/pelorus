# Architecture Docs

- [ ] TODO: document formal python version support policy
- [ ] TODO: do we want diagrams anywhere?

This documentation covers the design decisions behind Pelorus's code.

The [developer docs](https://pelorus.readthedocs.io/en/latest/Development/) are mainly about setting up a development environment, but we may move this in the future.

You may find docs for specific modules / packages in their respective folders.
For example, the [deserialization docs](../pelorus/deserialization/README.md) and [config loading docs](../pelorus/config/README.md).

# Common Libraries & Justification

## Attrs

We use attrs because it allows us to cut down on boilerplate,
and let us have easily correct dunder implementations (e.g. `__eq__`).

We use it instead of `dataclasses` because its converters and validators are useful to us.

## ExceptionGroup(s)

## typing_extensions

TODO: backports of typing stuff