"""A deliberate JSON Schema subset for ordinary typed Python signatures."""

from __future__ import annotations

import inspect
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import MISSING, dataclass, fields, is_dataclass
from enum import Enum
from functools import partial
from types import UnionType
from typing import (
	Annotated, Any, Literal, NotRequired, Required, Union,
	get_args, get_origin, get_type_hints, is_typeddict,
)

from .definition import metadata_dict
from .errors import MoveSchemaError

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def json_value(value: Any) -> Any:
	"""Copy a finite JSON value; enums use their declared value, never repr()."""
	if isinstance(value, Enum):
		return json_value(value.value)
	if is_dataclass(value) and not isinstance(value, type):
		return {item.name: json_value(getattr(value, item.name)) for item in fields(value)}
	if value is None or isinstance(value, (str, bool, int)):
		return value
	if isinstance(value, float) and math.isfinite(value):
		return value
	if isinstance(value, (list, tuple)):
		return [json_value(item) for item in value]
	if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
		return {key: json_value(item) for key, item in value.items()}
	raise MoveSchemaError("Value is not representable as finite JSON.")


def schema_for(
	annotation: Any,
	*,
	output: bool = False,
	_active: frozenset[type] = frozenset(),
) -> dict[str, Any]:
	"""Describe the supported annotation subset without constructing its values."""
	if annotation is Any:
		return {}
	for primitive, name in (
		(str, "string"), (bool, "boolean"), (int, "integer"),
		(float, "number"), (type(None), "null"),
	):
		if annotation is primitive:
			return {"type": name}
	origin = get_origin(annotation)
	arguments = get_args(annotation)
	if origin in (Annotated, Required, NotRequired):
		return schema_for(arguments[0], output=output, _active=_active)
	if origin in (Union, UnionType):
		return {"anyOf": [schema_for(item, output=output, _active=_active) for item in arguments]}
	if isinstance(annotation, type) and (is_dataclass(annotation) or is_typeddict(annotation)):
		if annotation in _active:
			raise MoveSchemaError("Recursive models need an explicit adapter schema.")
		active = _active | {annotation}
		try:
			hints = get_type_hints(annotation, include_extras=True)
		except Exception as error:
			raise MoveSchemaError("Model annotations could not be resolved.") from error
		properties = {}
		required = []
		if is_typeddict(annotation):
			for name, hint in hints.items():
				properties[name] = schema_for(hint, output=output, _active=active)
				origin = get_origin(hint)
				if origin is Required or (origin is not NotRequired and name in annotation.__required_keys__):
					required.append(name)
		else:
			model_fields = fields(annotation)
			if not output:
				try:
					constructor = inspect.signature(annotation)
				except (TypeError, ValueError) as error:
					raise MoveSchemaError("Dataclass constructor signature is unavailable.") from error
				init_names = {item.name for item in model_fields if item.init}
				if set(constructor.parameters) != init_names or any(
					parameter.kind not in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
					for parameter in constructor.parameters.values()
				):
					raise MoveSchemaError("Dataclass constructors must accept exactly their init fields by keyword.")
			for item in model_fields:
				if not output and not item.init:
					continue
				property_schema = schema_for(hints[item.name], output=output, _active=active)
				if output or (item.default is MISSING and item.default_factory is MISSING):
					required.append(item.name)
				if item.default is not MISSING:
					property_schema["default"] = json_value(item.default)
				properties[item.name] = property_schema
		return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}
	if origin is Literal:
		values = [json_value(item) for item in arguments]
		if any(isinstance(value, (list, dict)) for value in values):
			raise MoveSchemaError("Literal values must be JSON scalars.")
		return {"enum": values}
	if isinstance(annotation, type) and issubclass(annotation, Enum):
		values = [json_value(item.value) for item in annotation]
		if not values or any(isinstance(value, (list, dict)) for value in values):
			raise MoveSchemaError("Enums must contain JSON scalar values.")
		return {"enum": values}
	if annotation is list or origin in (list, Sequence):
		return {"type": "array", "items": schema_for(arguments[0], output=output, _active=_active) if arguments else {}}
	if annotation is dict or origin in (dict, Mapping):
		if arguments and arguments[0] is not str:
			raise MoveSchemaError("JSON object annotations require string keys.")
		return {
			"type": "object",
			"additionalProperties": schema_for(arguments[1], output=output, _active=_active) if arguments else {},
		}
	raise MoveSchemaError("Unsupported or unresolved annotation; supply an explicit schema.")


def callable_hints(func: Callable[..., Any]) -> dict[str, Any]:
	"""Resolve annotations from trusted Python code, including callable instances."""
	while isinstance(func, partial):
		func = func.func
	if inspect.isclass(func):
		func = func.__init__
	elif not (inspect.isfunction(func) or inspect.ismethod(func) or inspect.isbuiltin(func)):
		func = func.__call__
	return get_type_hints(func, include_extras=True)


@dataclass(frozen=True, slots=True)
class CallableSchemas:
	input_schema: dict[str, Any] | None
	output_schema: dict[str, Any] | None
	errors: tuple[str, ...]


def describe_schemas(
	func: Callable[..., Any],
	*,
	input_schema: Mapping[str, Any] | None = None,
	output_schema: Mapping[str, Any] | None = None,
) -> CallableSchemas:
	"""Infer each schema independently; unsupported Python remains directly usable."""
	errors: list[str] = []
	input_result = metadata_dict(input_schema) if input_schema is not None else None
	output_result = metadata_dict(output_schema) if output_schema is not None else None
	if input_schema is not None and output_schema is not None:
		return CallableSchemas(input_result, output_result, ())
	try:
		signature = inspect.signature(func)
	except (TypeError, ValueError):
		return CallableSchemas(input_result, output_result, ("Callable signature is unavailable.",))
	try:
		hints = callable_hints(func)
	except Exception as error:
		# Python forward annotations are trusted code, not an isolation boundary.
		hints = {}
		errors.append(f"Type annotations could not be resolved ({type(error).__name__}).")

	if input_schema is None:
		properties = {}
		required = []
		input_errors = []
		for name, parameter in signature.parameters.items():
			if parameter.kind in (
				inspect.Parameter.POSITIONAL_ONLY,
				inspect.Parameter.VAR_POSITIONAL,
				inspect.Parameter.VAR_KEYWORD,
			):
				input_errors.append(f"Input {name!r}: positional-only and variadic parameters need an explicit adapter.")
				continue
			annotation = hints.get(name, parameter.annotation)
			try:
				if annotation is inspect.Parameter.empty:
					raise MoveSchemaError("Missing type annotation; supply an explicit schema.")
				property_schema = schema_for(annotation)
				if parameter.default is inspect.Parameter.empty:
					required.append(name)
				else:
					property_schema["default"] = json_value(parameter.default)
				properties[name] = property_schema
			except (MoveSchemaError, RecursionError) as error:
				input_errors.append(f"Input {name!r}: {error}")
		if not input_errors:
			input_result = {
				"$schema": SCHEMA_DIALECT,
				"type": "object",
				"properties": properties,
				"required": required,
				"additionalProperties": False,
			}
		errors.extend(input_errors)

	if output_schema is None:
		annotation = hints.get("return", signature.return_annotation)
		try:
			if annotation is inspect.Signature.empty:
				raise MoveSchemaError("Missing return annotation; supply an explicit schema.")
			output_result = {"$schema": SCHEMA_DIALECT, **schema_for(annotation, output=True)}
		except (MoveSchemaError, RecursionError) as error:
			errors.append(f"Output: {error}")
	return CallableSchemas(input_result, output_result, tuple(errors))
