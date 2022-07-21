# What is `pelorus.config`?

A declarative way to load configuration from environment variables, and log that configuration properly.

See [the README](./README.md) for more details.

# How does it work?

`attrs` lets you declaratively create python classes with minimal boilerplate.
This concept was so popular a similar tool was added to python in the `dataclasses` module.

It also lets you easily do some metaprogramming: you can inspect each field of the class,
what type it was declared as, its name, and any optional metadata attached to it.

These factors combined make it easy to look for environment variables of the same name,
and know how to convert the type in a consistent way.

Knowing the name also makes it possible to guess what should be logged and what shouldn't be (credentials, etc).

Since you can pass metadata per field, you can configure the above behaviors.

# Why attrs instead of dataclasses?

attrs has some very attractive additional features over dataclasses.

Converters allow devs to customize how we convert configuration,
in case there's something more complex that needs to be handled,
or they need to deviate from the standard way of doing things.

Validators let devs... validate.

# Why load env vars yourself instead of using attrs's default factories?

Suppose the first required env var is missing.
The user makes a change, re-deploys the configuration,
waits for the pods to re-deploy...
only to find that they missed the second required env var.

Errors that can be reported in parallel absolutely should be reported in parallel.

This idea (in the abstract) is even acknowledged by python itself
in the upcoming "exception groups" feature.

# What is `NOTHING`?

In python, it's common to set a parameter's default to `None` to see if it wasn't passed anything.

However, there are cases where `None` is a perfectly valid value to pass,
so you can't rely on it meaning "no parameter was passed".

There is a common python idiom of using a "sentinel value",
usually made with something like `SENTINEL = object()`.

As for why it's re-exported in its own file, that's so typing tools such as mypy and pyright
can use it in a type signature, making sure the NOTHING case is handled.

This will be unnecessary if [the PR changing the typing](https://github.com/python-attrs/attrs/pull/983) is merged.

# Why are there so many type annotations? What are `.pyi` files?

mypy and pyright tools will type check python code.
They can catch _so many_ errors that would otherwise happen at runtime,
and provide even more helpful code completion / inline documentation support.
There's a reason why Guido Van Rossum is working so heavily on mypy!

`.pyi` files are "type stubs": they are checked for type information by typing tools,
but ignored at runtime.

We only use them for two things.

First, to use `NOTHING` as its own type (see above).

Secondly, for `attrs.Factory`.
Because a class's fields are marked as their runtime type (e.g. `str`, `bool`),
but `field` returns an `attrs.Attribute`, their type stubs have to lie about the
return value of both `field` and `attrs.Factory` to keep the type checker happy.
We undo that.