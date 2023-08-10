# Development Choices / Internal Architecture Docs

The [Architecture](./Architecture.md) docs cover the broader,
higher-level architecture of Pelorus: e.g. what talks to what and why.

Here you'll find notes about _internal architecture_:
how and why the code is structured the way it is,
libraries we made to support the project,
why we chose to use certain external libraries, etc.

Some formal development choices we made are available as
[ADRs](./Development.md#architectural-decision-records).


## `pelorus.config`

A declarative way to load configuration from environment variables,
and log that configuration properly.

For more information, see the [library docs](https://github.com/dora-metrics/pelorus/blob/master/exporters/pelorus/config/README.md).

### Why It Was Made

For exporter configuration and startup, we've experienced the following issues:
- It's always been ad-hoc and repetitious.
- As env vars evolve, we had to keep reassigning old ones for backwards compatibility.
- Configuration was not abstracted away from its source--
  changing to a config file instead of env vars would take a lot of work.
- Converting from strings to things such as lists was error-prone.
- Logging wasn't always done, leading to tons of time lost debugging.

### What It Does

- Takes an `attrs`-decorated class and looks for environment variables
  matching field names.
- Allows fallback env var names, optional fields, and defaults.
- Tells you from which env var the value came from (or if it's the default).
- Redacts any variable that looks like a credential by default
  (but is still manually configurable).

## `pelorus.deserialization`

A declarative deserialization and type checking framework that makes
handling heavily-nested data easy.

More detail can be found in the [library docs](https://github.com/dora-metrics/pelorus/blob/master/exporters/pelorus/deserialization/README.md).

### Why It Was Made and What We Tried

We have to work with data from OpenShift / Kubernetes.
You can't make static guarantees about those API definitions,
since they can change with what's installed on the cluster, etc.
It also means that type checking tools can't help us with that data.

As a real example, we need to get a commit author's name.
It's at `openshift_object.spec.revision.git.author.name`.
Note how nested it is-- 5 levels deep!

#### Background: the OpenShift Library

The OpenShift library makes it easier to write the above--
note that it's using attribute access, and not item access
(`.spec` instead of `["spec"]`). That's a convenience they added.
However, missing fields return `None` instead of raising an `AttributeError`.

#### Look Before You Leap (LBYL)

We can try checking each level of the data before continuing,
but that gets really verbose:

```python
if openshift_object.spec.revision is None:
    log.error("missing revision")
    return
if openshift_object.spec.revision.git is None:
    log.error("missing git")
    return
if openshift_object.spec.revision.git.author is None:
    log.error("missing author")
    return
    ...
# etc.
```

It's also error prone. Did you realize that we never checked if `openshift_object.spec is None`?  
You're also repeating yourself for each log message, and adding more context (about previous fields) is even more verbose.

#### Try It And See (TIAS)

We can try to assume the happy path, and catch any exceptions:

```python
try:
    name = openshift_object.spec.revision.git.author.name
    print(f"the author is {name}")
except AttributeError as e:
    log.error(e)
    return
```

Say that `author` isn't present. You'll get:  
`AttributeError: 'NoneType' object has no attribute name`.  
If that's surrounded by other code doing a ton of `.name`,
how easy is it to see that the error came from here?
Is there enough context?

You could put these checks around each level of access,
but that's just a more boilerplate-heavy LBYL.

If `name` is absent, you'll get `None`. Is that what you wanted?
Or were you expecting it to be present, and now you have to add
yet another `if name is None` check?

#### Repeating Yourself

You need to repeat the above for each new variable you access.

You also still have the type checking issue--
are you expecting a number, but got a string?
Did you remember to check for that manually?
If you just wrapped it in `int()`,
did you remember to check for `None`?

#### Failing Early, Failing Often

It's a way better user experience to report _all_ of the issues
at once. If we don't, it can be painful:

1. See there's an issue with the data or code.
2. Fix the issue with the data or code, which may take a while.
3. Redeploy, rerun, potentially waiting a long time.
4. Potentially GOTO 1.

### What It Does

- Deserializes and type-checks from mappings (dicts), iterables, and primitive values...
- To attrs classes, lists, dicts, and primitives (checked).
- Collects errors in parallel.
- Allows specifying deeply-nested data in attrs field metadata.
- Lets you keep the source you deserialized from for ease of use later.

## External Libraries & Why We Use Them

### attrs

We use [attrs](https://www.attrs.org/) because it allows us to cut down on boilerplate,
and let us have easily correct dunder implementations (e.g. `__eq__`).

We use it instead of `dataclasses` because its converters and validators are useful to us.

### exceptiongroup

The [exceptiongroup package](https://pypi.org/project/exceptiongroup/)
backports [`ExceptionGroup`s](https://peps.python.org/pep-0654/) to our version of python.
They are the official way to collect parallel errors and present them,
which is one of the core features of our deserialization package.

### typing_extensions

[`typing`](https://docs.python.org/3/library/typing.html) module gets better with every release of python.
The [typing_extensions](https://pypi.org/project/typing-extensions/)
package allows us to enjoy those improvements regardless of our version.