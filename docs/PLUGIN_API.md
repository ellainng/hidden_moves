# Implemented experimental plugin API

This records the first implementation of the design discussed in the project
notes. It is an experimental interface, without a stable compatibility promise.

## Dependency direction

`core/` uses only the Python standard library. Domain libraries and clients own
their behavior. `builtins.py` explicitly assembles library functions into move
definitions. `commands/` and `cli.py` adapt those definitions to Click.

The core owns no HTTP transport, file-writing policy, storage engine, credential
loading, or persistent service. These belong to ordinary libraries or applications.

## Definitions and registration

`MoveSpec` is a frozen dataclass with `name`, `func`, optional dotted `namespace`,
explicit `bind_target`, optional `target_types`, description, and provider source.
Names must be public Python identifiers. Names beginning with underscores and
Python keywords are rejected.

`Registry.register(spec)` registers one definition. `register_many(specs)` validates
the entire batch before publishing changes. A callable and a namespace cannot
occupy the same path. Container API names are reserved at the root. Duplicate
definitions fail unless replacement of that exact move is explicitly requested.

`Moves.learn(callable, ...)` builds and registers a definition. Functions normally
use their own names; callable objects need an explicit `name=`. Classes and existing
bound methods are also ordinary callables. No plugin base class is required.

## Binding and context

Each `Moves` container owns its target and a shallow copy of its context's outer
mapping. The outer context mapping is read-only; nested values and service objects
retain normal Python mutability. A registry can be shared independently.

`bind_target=True` binds the target as the first positional argument with partial
application. `Moves()` has no target, while `Moves(None)` has a real `None` target.
Declared target types are checked when target binding is requested; declaring types
alone never enables injection. Already-bound client methods normally leave binding
disabled. Context is never inferred from function parameter names or auto-injected.

Namespace proxies resolve through the registry without patching target objects,
target classes, or global state. `resolve()` supplies the same callable behavior as
attribute access. Unknown attributes raise `AttributeError`; unknown explicit
lookups raise `UnknownMoveError`. Missing or incompatible targets raise
`MoveBindingError`.

`explain()` inspects a move without calling it. Its `available` field reports target
binding compatibility, not dependency health, credentials, or remote service status.
Target and context values are excluded. Signatures may be unavailable for opaque
callables. Async metadata identifies declared coroutine functions and async callable
objects; synchronous functions may also return awaitables, which pass through unchanged.

## External providers

An external package advertises an integration in its own `pyproject.toml`:

```toml
[project.entry-points."hidden_moves.moves"]
example = "example_package.integration:provide_moves"
```

The current provider is a zero-argument callable returning an iterable of
`MoveSpec` objects. Its integration module can import Hidden Moves while the
underlying package remains independently usable.

`discover_providers()` returns installed entry-point metadata without importing
providers. `load_provider(entry, registry)` imports and invokes the selected
provider, then atomically registers its definitions with entry-point provenance.
Providers must keep imports and definition construction free of external side
effects. Create clients and acquire resources through explicit application setup or
capability invocation.

Provider import, definition, or collision failures raise `ProviderLoadError` with
the original cause. Existing registrations remain usable. A provider is an executable
Python integration, not an isolated process or sandbox.

The CLI lists metadata with `hidden-moves plugins list`. Explicit activation uses
`hidden-moves --plugin example moves list`. Provider state is limited to that CLI
invocation. Missing or ambiguous provider names fail before a provider is loaded.
External moves are available through the Python API and CLI inspection; arbitrary
Python signatures are not automatically converted into command-line arguments.

## Deferred decisions

Lifecycle hooks, dependency graphs, persistent registries, type-stub generation,
automatic CLI generation, Pydantic adapters, and stable plugin version negotiation
remain future work. Extract an independently useful capability before expanding
the provider contract around hypothetical requirements.
