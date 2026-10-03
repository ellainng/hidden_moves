"""Responses function tools consume the same selected catalog as other interfaces."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from hidden_moves import UnknownMoveError
from hidden_moves.adapters import CapabilityArgumentError, CapabilityCatalog, CapabilityExposureError

_TOOL_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_OMITTED_KEYWORDS = frozenset({"$schema", "default", "examples"})


def _parameters(schema: dict[str, Any]) -> dict[str, Any]:
	"""Drop declaration-only keywords without changing property names or enum values."""
	result = {key: value for key, value in schema.items() if key not in _OMITTED_KEYWORDS}
	if "properties" in result:
		result["properties"] = {name: _parameters(child) for name, child in result["properties"].items()}
	if "anyOf" in result:
		result["anyOf"] = [_parameters(child) for child in result["anyOf"]]
	for key in ("items", "additionalProperties"):
		if isinstance(result.get(key), dict):
			result[key] = _parameters(result[key])
	return result


def _enum_type(values: list[Any]) -> str | None:
	kinds = {
		"null" if value is None else "boolean" if type(value) is bool else
		"integer" if type(value) is int else "number" if type(value) is float else
		"string" if isinstance(value, str) else None
		for value in values
	}
	if kinds <= {"integer", "number"}:
		return "number" if "number" in kinds else "integer"
	return next(iter(kinds)) if len(kinds) == 1 else None


def _check_strict(schema: dict[str, Any], path: str = "$parameters") -> None:
	"""Accept a conservative subset without rewriting Python omission semantics."""
	def unsupported(reason: str) -> None:
		raise CapabilityExposureError(f"{path}: {reason}; use strict=False or a compatible callable/schema.")

	if "anyOf" in schema:
		if any(key in schema for key in ("type", "enum", "properties", "items")):
			unsupported("strict unions must use separate anyOf branches")
		for index, branch in enumerate(schema["anyOf"]):
			_check_strict(branch, f"{path}.anyOf[{index}]")
		return
	if "type" not in schema and "enum" in schema:
		kind = _enum_type(schema["enum"])
		if kind is not None:
			schema["type"] = kind
	types = schema.get("type")
	if types is None:
		unsupported("strict schemas require typed values")
	if isinstance(types, list):
		if len(types) != 2 or "null" not in types or len(set(types)) != 2:
			unsupported("strict type lists must contain one type and null")
	else:
		types = [types]
	if "object" in types:
		if schema.get("additionalProperties") is not False:
			unsupported("strict objects must reject additional properties")
		properties = schema.get("properties", {})
		if set(schema.get("required", ())) != set(properties):
			unsupported("strict objects must require every property")
		for name, child in properties.items():
			_check_strict(child, f"{path}.{name}")
	if "array" in types:
		if "items" not in schema:
			unsupported("strict arrays require an item schema")
		_check_strict(schema["items"], f"{path}.items")


class FunctionToolAdapter:
	"""Export Responses tool dictionaries and execute calls in the caller's loop."""

	def __init__(
		self,
		catalog: CapabilityCatalog,
		*,
		tool_names: Mapping[str, str] | None = None,
		strict: bool = False,
	) -> None:
		if type(strict) is not bool:
			raise TypeError("strict must be a boolean.")
		self.catalog = catalog
		aliases = dict(tool_names or {})
		selected = {definition.name for definition in catalog.definitions()}
		if set(aliases) - selected:
			raise ValueError("Tool aliases must reference selected capabilities.")
		self._names: dict[str, str] = {}
		tools = []
		for definition in catalog.definitions():
			name = aliases.get(definition.name, definition.name.replace(".", "__"))
			if not isinstance(name, str) or not _TOOL_NAME.fullmatch(name):
				raise ValueError("Function tool names require 1-64 ASCII letters, digits, underscores, or hyphens; supply an alias.")
			if name in self._names:
				raise ValueError(f"Function tool name collision: {name!r}.")
			parameters = _parameters(definition.to_dict()["input_schema"])
			if strict:
				_check_strict(parameters)
			tool = {"type": "function", "name": name, "parameters": parameters, "strict": strict}
			if definition.description is not None:
				tool["description"] = definition.description
			tools.append(tool)
			self._names[name] = definition.name
		self._tools = tuple(tools)

	def tools(self) -> list[dict[str, Any]]:
		"""Return fresh flat Responses definitions, ready for an application's request."""
		return deepcopy(list(self._tools))

	async def call(self, name: str, arguments: str | Mapping[str, Any]) -> str:
		"""Validate selected arguments, await when needed, and return finite JSON text."""
		try:
			qualified_name = self._names[name]
		except KeyError as error:
			raise UnknownMoveError(f"Function tool {name!r} is not selected in this adapter.") from error
		if isinstance(arguments, str):
			try:
				arguments = json.loads(arguments)
			except (ValueError, RecursionError) as error:
				raise CapabilityArgumentError("Function arguments must be valid JSON.") from error
		result = self.catalog.invoke(qualified_name, arguments)
		if inspect.isawaitable(result):
			result = await result
		value = self.catalog.serialize_result(qualified_name, result)
		return json.dumps(value, ensure_ascii=False, allow_nan=False)

	async def call_output(self, call_id: str, name: str, arguments: str | Mapping[str, Any]) -> dict[str, str]:
		"""Build the application's function_call_output item without contacting an API."""
		if not isinstance(call_id, str) or not call_id:
			raise ValueError("call_id must be a nonempty string.")
		return {"type": "function_call_output", "call_id": call_id, "output": await self.call(name, arguments)}
