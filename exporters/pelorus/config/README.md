# pelorus.config

A declarative way to load configuration from environment variables, and log that configuration properly.

Configuration needs to be consistent, and easy to get right.
Configuration should be logged in order to make debugging easier.
However, accidentally logging sensitive information (API credentials, etc.) must be hard.

This module handles the above goals by using `attrs`.

# Background

When it comes to exporter configuration and startup, we've experienced the following issues:
- It's always been ad-hoc and repetitious.
- As env vars evolve, we had to keep reassigning old ones for backwards compatibility.
- Configuration was not abstracted away from its source--
  changing to a config file instead of env vars would take a lot of work.
- Converting from strings to things such as lists was error-prone.
- Logging wasn't always done, leading to tons of time lost debugging.

# Tutorial: Basic Usage

```python
from pelorus.config import load_and_log

config = load_and_log(ConfigClass)
```

`load_and_log` inspects a class set up by `attrs`,
loading values from the environment, and logging what was found.

It uses some common-sense defaults:
- an attribute's name in uppercase is the environment variable's name.
- attributes whose name contains something implying sensitive information
  (e.g. credentials end up in a variable called `token`) have their values redacted.
- private fields (starting with any number of underscores) are not logged at all.

What does `ConfigClass` look like?

```python
from attrs import define

@define(kw_only=True)
class ConfigClass:
    username: str = "GVR"
    password: str
```

`load_and_log` will do the following:

1. Look for the environment variable `USERNAME`. If missing, it will be set to `GVR`.
2. Look for the environment variable `PASSWORD`.
3. Log the config class's name, the values obtained, and where the values came from:
  1. `username=GVR, default value; USERNAME was not set`
  2. `password=REDACTED, from env var PASSWORD`
4. Call `MyConfiguration(...)`:
  If `USERNAME` is missing, it will default to `GVR`.
  If `PASSWORD` is missing, a MissingConfigDataError will be thrown.

`kw_only=True` is requires so we can have a mandatory field after one with a default.
We recommend its use even if that doesn't apply to you.


# Tutorial: Advanced Usage

What if you need to:
- [Use a different environment variable name? Or check multiple env vars, for backwards compatibility?](#environment-variables)
- [Skip or recact a field that wouldn't normally be? Or the opposite?](#logging)
- [Use a datatype that isn't a string? Have a default for that when it's mutable?](#converters)
- [Use a value that isn't easily loaded from the environment?](#the-other-dict)

## Metadata

`attrs` lets you attach metadata to any field with just a simple dictionary.

We expose helpers for customizing log and environent variable lookup .

### Environment Variables

```python
from attrs import define, field
from pelorus.config import env_vars

@define(kw_only=True)
class EnvVarExample:
    different_variable_name: str = field(default="foo", metadata=env_vars("DIFF_VAR"))
    fallback_var_names: str = field(metadata=env_vars("NEW_VAR", "LEGACY_VAR"))
```

Loading this will check `DIFF_VAR` for the first field, instead of `DIFFERENT_VARIABLE_NAME`. It still has a default.

`fallback_var_names` will be set to whatever the earliest set env var is from the listed ones. e.g. if both are set, the value from `NEW_VAR` will be used.
If neither are set, an error will be logged and thrown.

### Logging

```python
from attrs import define, field
from pelorus.config import log, LOG, SKIP, REDACT

@define(kw_only=True)
class LogExample:
    test_to_pass: str = field(metadata=log(LOG))
    _dont_skip_me: str = field(metadata=log(LOG))
    i_am_sensitive: str = field(metadata=log(REDACT))
    do_skip_me: str = field(metadata=log(SKIP))
```

The value of `test_to_pass` would normally be redacted, because `pass` is in the field name. With the log metadata, that behavior is overridden.
`_dont_skip_me` would normally not appear in the logs at all because it is "private", but that is overridden.
`i_am_sensitive` _would_ normally appear in the logs, because there's no member of `REDACT_WORDS` in it. We have forced it to be redacted.
`do_skip_me` has been manually set to not appear in the logs at all.


### Combining metadata

What if you need to customize logging and env var metadata?
The metadata helpers expose metadata as a dict for convenience--
this means you can combine them with the dict union operator `|`.

```python
from attrs import define, field
from pelorus.config import log, REDACT, env_vars
@define
class CombinedClass:
    foo: str = field(metadata=log(REDACT) | env_vars("BAR"))
```

## Converters

`attrs` lets incoming values be automatically converted.
Since we load from environment variables, conversion is
necessary if the desired value's type is not a string!

We offer a helper for the common case, where a collection
takes a comma separated list of (whitespace-stripped) strings:

```python
from attrs import define, field
from attrs.converters import to_bool
from pelorus.config.converters import comma_separated

@define
class GiveMeCollections:
    namespaces: set[str] = field(factory=set, converter=comma_separated(set))
    foo: list[str] = field(factory=list, converter=comma_separated(list))
    tls_verify: bool = field(default="yes", converter=to_bool)
```

Note that we use `factory` instead of `default` for the collections.
This is because of python's "mutable defaults" gotcha:
if we set `default` to `[]`, _every instance of the class would use the same list!_

Also note how `tls_verify` uses a string default.
Even defaults go through converters.
Well-behaved converters will handle when their inputs are the same desired type,
and pass them through as-is. This is true for both to_bool and comma_separated,
so we could have written `default=True` if we wanted to.

`attrs` has some more converters defined, and even ways to compose them.
See their docs for details.

## The `other` dict

What if you have some data type that couldn't be loaded from the environment
(in our most common case, an openshift client)?

That can be passed in with `load_and_log`'s `other` dict.

```python
from attrs import define, field
from pelorus.config import no_env_vars

@define
class UsesOpenshift:
    client: object = field(metadata=no_env_vars())

_ = load_and_log(UsesOpenshift, other=dict(client=SOME_CLIENT_HERE))
```

Fields meant to be provided through `other` are not logged.
You can override this behavior.

## Customizing Init

Although `attrs` will generate an `__init__` for the class,
sometimes you need to deviate from this behavior.
Maybe you have a field that you need to create based on two other fields?
Or something to log after being set up?
Or need to validate the whole thing, not just a field or two?

See [attrs's docs on hooking into init](https://www.attrs.org/en/stable/init.html#hooking-yourself-into-initialization)
to learn how.

As a simple example:

```python
from attrs import define, field
from requests import Session

@define
class RequestsUser:
    api_user: str
    token: str

    _session: Session = field(factory=Session, init=False)

    def __attrs_post_init__(self):
        self._session.auth = (self.api_user, self.api_token)
```

Note that we still declare the field. This is nice for type checking tools,
but is also necessary because attrs uses `__slots__` unless told not to
in `define`'s arguments.

## Other attrs features

See the [`attrs` docs](https://www.attrs.org/en/stable/overview.html) to learn more
about its other features, including:
- validators
- frozen instances (a good idea!)

# Reference

See the pydoc for each item for more details.

You can also see the [unit test](../../tests/test_config.py) for more examples.

# Development

See [DEVELOPING.md](./DEVELOPING.md) for details.