"""Protocol-neutral capability descriptions and behavioral hints."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import Any


def freeze_metadata(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
	"""Copy JSON-compatible metadata into immutable mappings and tuples."""
	if not isinstance(metadata, Mapping):
		raise TypeError("metadata must be a mapping with string keys.")
	active: set[int] = set()

	def freeze(value: Any) -> Any:
		if value is None or isinstance(value, (str, bool, int)):
			return value
		if isinstance(value, float) and math.isfinite(value):
			return value
		if isinstance(value, (Mapping, list, tuple)):
			identity = id(value)
			if identity in active:
				raise ValueError("metadata must not contain circular references.")
			active.add(identity)
			try:
				if isinstance(value, Mapping):
					if not all(isinstance(key, str) for key in value):
						raise TypeError("metadata keys must be strings.")
					return MappingProxyType({key: freeze(item) for key, item in value.items()})
				return tuple(freeze(item) for item in value)
			finally:
				active.remove(identity)
		raise TypeError("metadata values must be finite JSON-compatible values.")

	return freeze(metadata)


def metadata_dict(metadata: Mapping[str, Any]) -> dict[str, Any]:
	"""Return a fresh JSON-compatible view without exposing mutable internals."""
	def thaw(value: Any) -> Any:
		if isinstance(value, Mapping):
			return {key: thaw(item) for key, item in value.items()}
		if isinstance(value, tuple):
			return [thaw(item) for item in value]
		return value

	return thaw(metadata)


@dataclass(frozen=True, slots=True)
class MoveAnnotations:
	"""Descriptive hints, never authorization; None means the behavior is unknown."""

	read_only: bool | None = None
	destructive: bool | None = None
	idempotent: bool | None = None
	external: bool | None = None

	def __post_init__(self) -> None:
		for item in fields(self):
			value = getattr(self, item.name)
			if value is not None and not isinstance(value, bool):
				raise TypeError(f"{item.name} must be a boolean or None.")

	def to_dict(self) -> dict[str, bool | None]:
		return {item.name: getattr(self, item.name) for item in fields(self)}


@dataclass(frozen=True, slots=True)
class MoveDefinition:
	"""An inspectable capability in one container, without target/context values."""

	name: str
	source: str
	description: str
	signature: str | None
	bind_target: bool
	target_types: tuple[str, ...]
	is_async: bool
	available: bool
	binding_error: str | None
	annotations: MoveAnnotations = field(default_factory=MoveAnnotations)
	metadata: Mapping[str, Any] = field(default_factory=dict)
	input_schema: Mapping[str, Any] | None = None
	output_schema: Mapping[str, Any] | None = None
	schema_errors: tuple[str, ...] = ()

	def __post_init__(self) -> None:
		object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
		for name in ("input_schema", "output_schema"):
			value = getattr(self, name)
			if value is not None:
				object.__setattr__(self, name, freeze_metadata(value))

	def to_dict(self) -> dict[str, Any]:
		return {
			"name": self.name,
			"source": self.source,
			"description": self.description,
			"signature": self.signature,
			"bind_target": self.bind_target,
			"target_types": self.target_types,
			"is_async": self.is_async,
			"available": self.available,
			"binding_error": self.binding_error,
			"annotations": self.annotations.to_dict(),
			"metadata": metadata_dict(self.metadata),
			"input_schema": metadata_dict(self.input_schema) if self.input_schema is not None else None,
			"output_schema": metadata_dict(self.output_schema) if self.output_schema is not None else None,
			"schema_errors": self.schema_errors,
		}
