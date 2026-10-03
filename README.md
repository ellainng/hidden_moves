# Hidden Moves

Hidden Moves collects reusable Python capabilities and exposes them through a small
registry, per-object binding, and an optional CLI. Functions and clients remain
useful through ordinary imports; they do not need to inherit from Hidden Moves classes.

The API is experimental. See [the implemented plugin contract](docs/PLUGIN_API.md)
for registration, binding, discovery, and extraction boundaries.

## Setup and commands

Python 3.11 or newer is required. Click is the only production dependency.

```sh
uv sync
uv run hidden-moves --help
uv run hidden-moves moves list
uv run hidden-moves moves show io.json.dumps
uv run hidden-moves text slugify 'Héllo, World!'
uv run hidden-moves json dumps '{"value": 1}' --indent 2
uv run hidden-moves cmd run ls -lahC .
uv run hidden-moves plugins list
uv run hm moves list
```

The `hm` command is a short alias for `hidden-moves`. For the current checkout without
installing the package, use `PYTHONPATH=src .venv/bin/python -m hidden_moves`.

## 1. Ordinary functions

Registration defaults to preserving the original arguments. Built-in definitions
are assembled explicitly; creating `Moves()` gives you an empty registry.

```python
from hidden_moves import Moves
from hidden_moves.kit.text import slugify

moves = Moves()
moves.learn(
	slugify,
	namespace="text",
)

assert moves.text.slugify("Héllo, World!") == slugify("Héllo, World!")
```

## 2. Target-bound serialization

`bind_target=True` supplies the current target as the callable's first positional
argument. The target and its class are not modified. Multiple containers can share
the same definitions while binding different targets.

```python
from hidden_moves import Moves
from hidden_moves.builtins import builtin_registry

registry = builtin_registry()
first = Moves(
	target={
		"value": 1,
	},
	registry=registry,
)
second = Moves(
	target={
		"value": 2,
	},
	registry=registry,
)

print(first.io.json.dumps(indent=2))
print(second.io.json.dumps(indent=2))
```

## 3. Configured clients

Configuration is explicit. A client factory can read a container's context, and
its existing bound method can be learned without injecting another target.
Constructing this client and registering its method perform no network I/O;
calling `get()` makes the request. Replace the example URL with your service.

```python
from hidden_moves import Moves
from hidden_moves.connectors.json_api import JsonApiClient

moves = Moves(
	context={
		"api": {
			"base_url": "https://api.example.test/v1/",
			"timeout": 5.0,
		},
	},
)
client = JsonApiClient(
	**moves.context["api"],
)
moves.learn(
	client.get,
	namespace="api",
)

result = moves.api.get("items")
```

The small JSON client supports GET requests, headers, query parameters, a finite
timeout, and an injected opener. HTTP, transport, and JSON decoding errors propagate
to the application. Authentication, retries, and pagination remain client concerns.

The existing Obsidian exporter is also available directly as
`hidden_moves.notes.obsidian.export_index(vault, destination=None)` and as the
explicit built-in move `notes.obsidian.export_index`.

## Inspection and async

- `moves.moves()` returns definitions sorted by qualified name.
- `moves.knows("io.json.dumps")` reports registration, including unbound moves.
- `moves.resolve("io.json.dumps")` returns the callable for this target.
- `moves.describe("io.json.dumps")` returns a structured `MoveDefinition`.
- `moves.explain("io.json.dumps")` reports source, signature, binding, and async metadata.
- `dir(moves)` and `dir(moves.io)` include registered namespace members.

Async callables retain their awaitable results. Use `await moves.operation(...)`;
Hidden Moves does not run an event loop on your behalf. Dynamic namespace access
does not promise static autocomplete; the underlying typed APIs remain available.

Registration can include `MoveAnnotations(read_only=True, destructive=False)` and
JSON-compatible `metadata`. Behavioral hints default to unknown and leave invocation
policy to consumers. Metadata is copied deeply and stored immutably. Descriptions
retain full documentation; inspection never displays target or context values.

## Tests and lint

Focused behavior tests live in `tests/` and use standard-library `unittest`.
The client tests inject a transport and make no real network requests.
Pull requests also build and install the package, run the behavior suite on
Python 3.11 and 3.13, and check both installed commands and module execution.

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
uvx ruff check src/hidden_moves/core src/hidden_moves/commands \
  src/hidden_moves/connectors/json_api.py src/hidden_moves/kit/cmd \
  src/hidden_moves/kit/text.py src/hidden_moves/notes/obsidian.py \
  src/hidden_moves/builtins.py src/hidden_moves/cli.py \
  src/hidden_moves/__init__.py src/hidden_moves/__main__.py tests
```
