"""Select, inspect, and invoke capabilities without protocol or event-loop policy."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType, UnionType
from typing import Annotated, Any, Union, get_args, get_origin

from hidden_moves import MoveDefinition, Moves, MoveSchemaError, UnknownMoveError
from hidden_moves.core.schema import callable_hints, json_value, schema_for

from ._validation import ValueValidationError, check_schema, validate_value
from .errors import CapabilityArgumentError, CapabilityExposureError, CapabilityResultError


def _python_value(annotation: Any, value: Any) -> Any:
	"""Restore enum values and lossless integers at the JSON-to-Python boundary."""
	origin = get_origin(annotation)
	arguments = get_args(annotation)
	if origin is Annotated:
		return _python_value(arguments[0], value)
	if origin in (Union, UnionType):
		for option in arguments:
			try:
				validate_value(schema_for(option), value)
				return _python_value(option, value)
			except (ValueValidationError, MoveSchemaError):
				continue
	if isinstance(annotation, type) and issubclass(annotation, Enum):
		return annotation(value)
	if annotation is int and type(value) is float and value.is_integer():
		return int(value)
	if origin in (list, Sequence) and arguments and isinstance(value, list):
		return [_python_value(arguments[0], item) for item in value]
	if origin in (dict, Mapping) and arguments and isinstance(value, dict):
		return {key: _python_value(arguments[1], item) for key, item in value.items()}
	return value


@dataclass(frozen=True, slots=True)
class _Capability:
	definition: MoveDefinition
	func: Callable[..., Any]
	signature: inspect.Signature
	hints: Mapping[str, Any]


class CapabilityCatalog:
	"""A snapshot of explicitly selected definitions and their bound callables."""

	def __init__(self, moves: Moves, names: Iterable[str]) -> None:
		if isinstance(names, str):
			raise TypeError("names must be an iterable of qualified names, not one string.")
		names = tuple(names)
		if not all(isinstance(name, str) for name in names):
			raise TypeError("Selected names must be strings.")
		entries = {}
		for name in sorted(set(names)):
			definition = moves.describe(name)
			if not definition.available:
				raise CapabilityExposureError(definition.binding_error)
			if definition.input_schema is None:
				raise CapabilityExposureError(f"{name!r} has no supported input schema: {'; '.join(definition.schema_errors)}")
			check_schema(definition.input_schema)
			if definition.output_schema is not None:
				check_schema(definition.output_schema)
			func = moves.resolve(name)
			try:
				signature = inspect.signature(func)
			except (TypeError, ValueError) as error:
				raise CapabilityExposureError(f"{name!r} has no usable signature.") from error
			if any(parameter.kind in (
				inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.VAR_POSITIONAL,
			) for parameter in signature.parameters.values()):
				raise CapabilityExposureError(f"{name!r} needs an explicit adapter for positional-only or variadic arguments.")
			try:
				hints = callable_hints(func)
			except Exception:
				hints = {}
			entries[name] = _Capability(definition, func, signature, MappingProxyType(hints))
		self._entries = MappingProxyType(entries)

	def _entry(self, name: str) -> _Capability:
		try:
			return self._entries[name]
		except KeyError as error:
			raise UnknownMoveError(f"Capability {name!r} is not selected in this catalog.") from error

	def definitions(self) -> tuple[MoveDefinition, ...]:
		return tuple(entry.definition for entry in self._entries.values())

	def describe(self, name: str) -> MoveDefinition:
		return self._entry(name).definition

	def invoke(self, name: str, arguments: Mapping[str, Any]) -> Any:
		"""Validate before calling; return ordinary results and awaitables unchanged."""
		entry = self._entry(name)
		try:
			if not isinstance(arguments, Mapping):
				raise ValueValidationError("Arguments must be an object.")
			values = json_value(arguments)
			validate_value(entry.definition.input_schema, values)
			values = {key: _python_value(entry.hints.get(key, Any), value) for key, value in values.items()}
			entry.signature.bind(**values)
		except (ValueValidationError, MoveSchemaError, TypeError, ValueError, RecursionError) as error:
			raise CapabilityArgumentError(str(error)) from error
		return entry.func(**values)

	def serialize_result(self, name: str, result: Any) -> Any:
		"""Copy a finite JSON result and check its declared output schema, if present."""
		entry = self._entry(name)
		try:
			value = json_value(result)
			if entry.definition.output_schema is not None:
				validate_value(entry.definition.output_schema, value, "$result")
			return value
		except (MoveSchemaError, ValueValidationError, RecursionError) as error:
			raise CapabilityResultError(str(error)) from error
