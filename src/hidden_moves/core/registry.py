"""Deterministic registration without application or target state."""

from __future__ import annotations

from collections.abc import Iterable

from .errors import MoveCollisionError, UnknownMoveError
from .spec import MoveSpec

# These are the public attributes of the root Moves container.
_RESERVED_ROOT_NAMES = frozenset({
	"context",
	"explain",
	"knows",
	"learn",
	"moves",
	"registry",
	"resolve",
	"target",
})


class Registry:
	"""Own move definitions; share a registry without sharing bound targets."""

	def __init__(self) -> None:
		self._specs: dict[str, MoveSpec] = {}

	def register(self, spec: MoveSpec, *, replace: bool = False) -> MoveSpec:
		if not isinstance(spec, MoveSpec):
			raise TypeError("Registry.register expects a MoveSpec; use Moves.learn for callables.")
		name = spec.qualified_name
		root = name.split(".", 1)[0]
		if root in _RESERVED_ROOT_NAMES:
			raise MoveCollisionError(f"{root!r} is reserved by the Moves container.")
		if name in self._specs and not replace:
			raise MoveCollisionError(f"Move {name!r} is already registered.")
		components = name.split(".")
		for index in range(1, len(components)):
			prefix = ".".join(components[:index])
			if prefix in self._specs:
				raise MoveCollisionError(f"Move {prefix!r} cannot also be a namespace.")
		if self.children(name):
			raise MoveCollisionError(f"Namespace {name!r} cannot also be a move.")
		self._specs[name] = spec
		return spec

	def register_many(
		self,
		specs: Iterable[MoveSpec],
		*,
		replace: bool = False,
	) -> tuple[MoveSpec, ...]:
		"""Validate a whole batch before publishing any of its definitions."""
		pending = Registry()
		pending._specs = self._specs.copy()
		registered = tuple(pending.register(spec, replace=replace) for spec in specs)
		self._specs = pending._specs
		return registered

	def resolve(self, name: str) -> MoveSpec:
		try:
			return self._specs[name]
		except KeyError as error:
			raise UnknownMoveError(f"Unknown move: {name!r}.") from error

	def knows(self, name: str) -> bool:
		return name in self._specs

	def specs(self) -> tuple[MoveSpec, ...]:
		return tuple(self._specs[name] for name in sorted(self._specs))

	def children(self, namespace: str = "") -> tuple[str, ...]:
		prefix = f"{namespace}." if namespace else ""
		return tuple(sorted({
			name[len(prefix):].split(".", 1)[0]
			for name in self._specs
			if name.startswith(prefix)
		}))
