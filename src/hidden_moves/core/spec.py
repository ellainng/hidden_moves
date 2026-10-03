"""Lightweight definitions for ordinary Python callables."""

from __future__ import annotations

import inspect
import keyword
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


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

	def __post_init__(self) -> None:
		_validate_component(self.name)
		if not callable(self.func):
			raise TypeError("A move must contain a callable.")
		if not isinstance(self.bind_target, bool):
			raise TypeError("bind_target must be a boolean.")
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
		return self.description or (inspect.getdoc(self.func) or "").partition("\n")[0]

	@property
	def is_async(self) -> bool:
		return inspect.iscoroutinefunction(self.func) or inspect.iscoroutinefunction(
			type(self.func).__call__
		)
