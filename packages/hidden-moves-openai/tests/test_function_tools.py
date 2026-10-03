"""Local function-tool export and dispatch through real selected catalogs."""

import asyncio
import json
import subprocess
import sys
import unittest
from dataclasses import dataclass
from typing import Any, Literal

from hidden_moves import MoveAnnotations, Moves, UnknownMoveError
from hidden_moves.adapters import (
	CapabilityArgumentError,
	CapabilityCatalog,
	CapabilityExposureError,
	CapabilityResultError,
)
from hidden_moves_openai import FunctionToolAdapter


def repeat(value: str, count: int = 2) -> str:
	"""Repeat a string."""
	return value * count


@dataclass
class Payload:
	value: str
	labels: list[str]


@dataclass
class OptionalPayload:
	value: str = "default"


def adapter_for(func, **options):
	moves = Moves()
	moves.learn(func, namespace="text", annotations=MoveAnnotations(read_only=True), metadata={"source": "test"})
	return FunctionToolAdapter(CapabilityCatalog(moves, [f"text.{func.__name__}"]), **options)


class FunctionToolExportTests(unittest.TestCase):
	def test_responses_format_preserves_catalog_and_omits_extra_fields(self):
		adapter = adapter_for(repeat)
		tool, = adapter.tools()
		self.assertEqual(tool["name"], "text__repeat")
		self.assertEqual(tool["type"], "function")
		self.assertEqual(tool["description"], "Repeat a string.")
		self.assertIs(tool["strict"], False)
		self.assertEqual(tool["parameters"]["required"], ["value"])
		self.assertEqual(tool["parameters"]["properties"]["count"], {"type": "integer"})
		self.assertEqual(set(tool), {"type", "name", "description", "parameters", "strict"})
		definition = adapter.catalog.describe("text.repeat").to_dict()
		self.assertEqual(definition["input_schema"]["properties"]["count"]["default"], 2)
		self.assertIn("$schema", definition["input_schema"])

	def test_exported_views_do_not_change_dispatch_or_future_exports(self):
		adapter = adapter_for(repeat)
		tools = adapter.tools()
		tools[0]["name"] = "changed"
		tools[0]["parameters"]["properties"]["value"]["type"] = "integer"
		self.assertEqual(adapter.tools()[0]["name"], "text__repeat")
		self.assertEqual(adapter.tools()[0]["parameters"]["properties"]["value"]["type"], "string")

	def test_schema_filter_preserves_property_names_that_match_keywords(self):
		def operation(default: str, examples: list[str]) -> str:
			return default

		properties = adapter_for(operation).tools()[0]["parameters"]["properties"]
		self.assertEqual(set(properties), {"default", "examples"})
		self.assertEqual(properties["examples"]["items"], {"type": "string"})

	def test_aliases_resolve_name_limits_and_collisions_only_when_explicit(self):
		moves = Moves()
		moves.learn(repeat, name="a__b")
		moves.learn(repeat, namespace="a", name="b")
		catalog = CapabilityCatalog(moves, ["a__b", "a.b"])
		with self.assertRaisesRegex(ValueError, "collision"):
			FunctionToolAdapter(catalog)
		adapter = FunctionToolAdapter(catalog, tool_names={"a.b": "qualified"})
		self.assertEqual({tool["name"] for tool in adapter.tools()}, {"qualified", "a__b"})
		for aliases in ({"missing": "alias"}, {"a.b": "with.dot"}, {"a.b": "x" * 65}):
			with self.subTest(aliases=aliases), self.assertRaises(ValueError):
				FunctionToolAdapter(catalog, tool_names=aliases)
		moves.learn(repeat, name="répéter")
		unicode_catalog = CapabilityCatalog(moves, ["répéter"])
		with self.assertRaises(ValueError):
			FunctionToolAdapter(unicode_catalog)
		self.assertEqual(FunctionToolAdapter(unicode_catalog, tool_names={"répéter": "repeat"}).tools()[0]["name"], "repeat")

	def test_strict_supports_closed_models_nullable_required_fields_and_enums(self):
		def operation(payload: Payload, mode: Literal["first", "second"], note: str | None) -> Payload:
			return payload

		adapter = adapter_for(operation, strict=True)
		parameters = adapter.tools()[0]["parameters"]
		self.assertIs(adapter.tools()[0]["strict"], True)
		self.assertEqual(parameters["required"], ["payload", "mode", "note"])
		self.assertEqual(parameters["properties"]["payload"]["required"], ["value", "labels"])
		self.assertEqual(parameters["properties"]["mode"]["type"], "string")
		self.assertNotIn("type", adapter.catalog.describe("text.operation").input_schema["properties"]["mode"])
		self.assertEqual(parameters["properties"]["note"]["anyOf"], [{"type": "string"}, {"type": "null"}])

	def test_strict_rejects_optional_open_untyped_and_mixed_enum_schemas(self):
		def optional(payload: OptionalPayload) -> str:
			return payload.value

		def mapping(values: dict[str, str]) -> dict[str, str]:
			return values

		def untyped(value: Any) -> Any:
			return value

		def mixed(value: Literal[1, "one"]) -> str:
			return str(value)

		for func in (repeat, optional, mapping, untyped, mixed):
			with self.subTest(func=func.__name__), self.assertRaises(CapabilityExposureError):
				adapter_for(func, strict=True)
			self.assertIs(adapter_for(func).tools()[0]["strict"], False)
		with self.assertRaises(TypeError):
			adapter_for(repeat, strict="true")

	def test_import_does_not_require_an_api_or_protocol_sdk(self):
		source = """
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'openai', 'mcp'}:
        raise AssertionError('optional SDK import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import hidden_moves_openai
"""
		result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=10)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertEqual(result.stdout, "")


class FunctionToolCallTests(unittest.IsolatedAsyncioTestCase):
	async def test_defaults_json_text_and_call_output_use_one_dispatch_path(self):
		adapter = adapter_for(repeat)
		self.assertEqual(json.loads(await adapter.call("text__repeat", '{"value": "hé"}')), repeat("hé"))
		self.assertEqual(await adapter.call_output("call-1", "text__repeat", {"value": "x", "count": 3}), {
			"type": "function_call_output", "call_id": "call-1", "output": '"xxx"',
		})
		with self.assertRaises(CapabilityArgumentError):
			await adapter.call("text__repeat", {"value": "x", "count": None})

	async def test_invalid_or_unselected_calls_fail_before_side_effects(self):
		calls = []

		def operation(value: int) -> int:
			calls.append(value)
			return value

		adapter = adapter_for(operation)
		for arguments in ("invalid", "[]", "null", "{}", '{"value": true}', '{"value": NaN}', {"value": "1"}, {"value": 1, "extra": 2}):
			with self.subTest(arguments=arguments), self.assertRaises(CapabilityArgumentError):
				await adapter.call("text__operation", arguments)
		with self.assertRaises(UnknownMoveError):
			await adapter.call("text.operation", {"value": 1})
		with self.assertRaises(ValueError):
			await adapter.call_output("", "text__operation", {"value": 1})
		self.assertEqual(calls, [])

	async def test_async_model_inputs_and_outputs_use_the_existing_loop(self):
		loop = asyncio.get_running_loop()

		async def operation(payload: Payload) -> Payload:
			self.assertIs(asyncio.get_running_loop(), loop)
			self.assertIsInstance(payload, Payload)
			await asyncio.sleep(0)
			return Payload(payload.value.upper(), payload.labels)

		adapter = adapter_for(operation, strict=True)
		self.assertEqual(json.loads(await adapter.call("text__operation", {"payload": {"value": "hello", "labels": ["first"]}})), {
			"value": "HELLO", "labels": ["first"],
		})

	async def test_capability_failures_result_errors_and_cancellation_propagate(self):
		def failure() -> str:
			raise RuntimeError("capability failure")

		def wrong() -> int:
			return "wrong type"

		def opaque() -> Any:
			return object()

		async def cancelled() -> None:
			raise asyncio.CancelledError

		for func, error in ((failure, RuntimeError), (wrong, CapabilityResultError), (opaque, CapabilityResultError), (cancelled, asyncio.CancelledError)):
			with self.subTest(func=func.__name__), self.assertRaises(error):
				await adapter_for(func).call(f"text__{func.__name__}", {})

	async def test_explicit_alias_dispatches_without_changing_the_catalog(self):
		adapter = adapter_for(repeat, tool_names={"text.repeat": "repeat_text"})
		self.assertEqual(json.loads(await adapter.call("repeat_text", {"value": "x"})), "xx")
		self.assertEqual(adapter.catalog.describe("text.repeat").name, "text.repeat")
		with self.assertRaises(UnknownMoveError):
			await adapter.call("text__repeat", {"value": "x"})
