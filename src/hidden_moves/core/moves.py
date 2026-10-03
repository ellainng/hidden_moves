"""Per-object capability access using proxies and partial application."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from functools import partial
from types import MappingProxyType
from typing import Any

from .definition import MoveAnnotations, MoveDefinition
from .errors import MoveBindingError
from .registry import Registry
from .spec import MoveSpec

_UNBOUND = object()


class _Namespace:
	__slots__ = ("_prefix", "_registry", "_target")

	def __init__(self, registry: Registry, target: Any, prefix: str = "") -> None:
		self._registry = registry
		self._target = target
		self._prefix = prefix

	def _bind(self, spec: MoveSpec) -> Callable[..., Any]:
		if not spec.bind_target:
			return spec.func
		if self._target is _UNBOUND:
			raise MoveBindingError(f"Move {spec.qualified_name!r} requires Moves(target=...).")
		if spec.target_types and not isinstance(self._target, spec.target_types):
			expected = ", ".join(target_type.__name__ for target_type in spec.target_types)
			raise MoveBindingError(
				f"Move {spec.qualified_name!r} requires a target of type {expected}; "
				f"got {type(self._target).__name__}."
			)
		return partial(spec.func, self._target)

	def __getattr__(self, name: str) -> Any:
		if name.startswith("_"):
			raise AttributeError(name)
		qualified_name = f"{self._prefix}.{name}" if self._prefix else name
		if self._registry.knows(qualified_name):
			return self._bind(self._registry.resolve(qualified_name))
		if self._registry.children(qualified_name):
			return _Namespace(self._registry, self._target, qualified_name)
		raise AttributeError(f"No move or namespace named {qualified_name!r}.")

	def __dir__(self) -> list[str]:
		return sorted(set(super().__dir__()) | set(self._registry.children(self._prefix)))


class Moves(_Namespace):
	"""Learn callables without modifying the target or its class.

	Configuration is available to application factories through context. It is
	never inferred from callable parameters or automatically injected into moves.
	"""

	__slots__ = ("_context",)

	def __init__(
		self,
		target: Any = _UNBOUND,
		*,
		registry: Registry | None = None,
		context: Mapping[str, Any] | None = None,
	) -> None:
		super().__init__(registry if registry is not None else Registry(), target)
		self._context = MappingProxyType(dict(context) if context is not None else {})

	@property
	def registry(self) -> Registry:
		return self._registry

	@property
	def context(self) -> Mapping[str, Any]:
		return self._context

	@property
	def target(self) -> Any:
		if self._target is _UNBOUND:
			raise MoveBindingError("This container has no target; supply Moves(target=...).")
		return self._target

	def learn(
		self,
		func: Callable[..., Any],
		*,
		name: str | None = None,
		namespace: str | None = None,
		bind_target: bool = False,
		target_types: tuple[type, ...] = (),
		description: str | None = None,
		provider: str | None = None,
		annotations: MoveAnnotations | None = None,
		metadata: Mapping[str, Any] | None = None,
		replace: bool = False,
	) -> MoveSpec:
		public_name = name if name is not None else getattr(func, "__name__", None)
		if public_name is None:
			raise ValueError("Supply name= for a callable without a __name__ attribute.")
		return self._registry.register(
			MoveSpec(
				name=public_name,
				func=func,
				namespace=namespace,
				bind_target=bind_target,
				target_types=target_types,
				description=description,
				provider=provider,
				annotations=annotations if annotations is not None else MoveAnnotations(),
				metadata=metadata if metadata is not None else {},
			),
			replace=replace,
		)

	def knows(self, name: str) -> bool:
		return self._registry.knows(name)

	def moves(self) -> tuple[MoveSpec, ...]:
		return self._registry.specs()

	def resolve(self, name: str) -> Callable[..., Any]:
		return self._bind(self._registry.resolve(name))

	def describe(self, name: str) -> MoveDefinition:
		"""Inspect a capability without invoking it or displaying target/config values."""
		spec = self._registry.resolve(name)
		binding_error = None
		func = spec.func
		try:
			func = self._bind(spec)
		except MoveBindingError as error:
			binding_error = str(error)
		try:
			signature = str(inspect.signature(func))
		except (TypeError, ValueError):
			signature = None
		return MoveDefinition(
			name=spec.qualified_name,
			source=spec.source,
			description=spec.documentation,
			signature=signature,
			bind_target=spec.bind_target,
			target_types=tuple(target_type.__name__ for target_type in spec.target_types),
			is_async=spec.is_async,
			available=binding_error is None,
			binding_error=binding_error,
			annotations=spec.annotations,
			metadata=spec.metadata,
		)

	def explain(self, name: str) -> dict[str, Any]:
		"""Return a fresh JSON-compatible view of a capability definition."""
		return self.describe(name).to_dict()
