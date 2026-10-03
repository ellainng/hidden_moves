"""Lightweight definitions for ordinary Python callables."""

from __future__ import annotations

import inspect
import keyword
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .definition import MoveAnnotations, freeze_metadata


def _validate_component(component: str) -> None:
	if (
		not isinstance(component, str)
		or not component.isidentifier()
		or component.startswith("_")
		or keyword.iskeyword(component)
	):
		raise ValueError(f"Move names must be public Python identifiers: {component!r}")


@dataclass(frozen=True, slots=True)
class MoveSpec:
	"""A callable and its public identity; target injection is always explicit."""

	name: str
	func: Callable[..., Any]
	namespace: str | None = None
	bind_target: bool = False
	target_types: tuple[type, ...] = ()
	description: str | None = None
	provider: str | None = None
	annotations: MoveAnnotations = field(default_factory=MoveAnnotations)
	metadata: Mapping[str, Any] = field(default_factory=dict)

	def __post_init__(self) -> None:
		_validate_component(self.name)
		if not callable(self.func):
			raise TypeError("A move must contain a callable.")
		if not isinstance(self.bind_target, bool):
			raise TypeError("bind_target must be a boolean.")
		if not isinstance(self.annotations, MoveAnnotations):
			raise TypeError("annotations must be MoveAnnotations.")
		for name in ("description", "provider"):
			value = getattr(self, name)
			if value is not None and not isinstance(value, str):
				raise TypeError(f"{name} must be a string or None.")
		object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
		if self.namespace is not None:
			if not isinstance(self.namespace, str):
				raise TypeError("A namespace must be a dotted string or None.")
			for component in self.namespace.split("."):
				_validate_component(component)
		if not isinstance(self.target_types, tuple) or not all(
			isinstance(target_type, type) for target_type in self.target_types
		):
			raise TypeError("target_types must be a tuple of runtime types.")

	@property
	def qualified_name(self) -> str:
		return f"{self.namespace}.{self.name}" if self.namespace else self.name

	@property
	def source(self) -> str:
		return self.provider or getattr(self.func, "__module__", type(self.func).__module__)

	@property
	def summary(self) -> str:
		return self.documentation.partition("\n")[0]

	@property
	def documentation(self) -> str:
		return self.description if self.description is not None else (inspect.getdoc(self.func) or "")

	@property
	def is_async(self) -> bool:
		return inspect.iscoroutinefunction(self.func) or inspect.iscoroutinefunction(
			type(self.func).__call__
		)
