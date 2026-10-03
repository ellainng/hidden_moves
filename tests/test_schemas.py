"""Typed schema boundaries, binding, defaults, and explicit diagnostics."""

from __future__ import annotations

import json
import unittest
from enum import Enum
from typing import Any, Literal

from hidden_moves import Moves, MoveSpec


class Color(Enum):
	RED = "red"
	BLUE = "blue"


class SchemaTests(unittest.TestCase):
	def describe(self, func, **options):
		moves = Moves()
		moves.learn(func, name="operation", **options)
		return moves.describe("operation").to_dict()

	def test_primitives_keyword_only_defaults_and_nullable_required_values(self):
		def operation(name: str, count: int | None, *, enabled: bool = False, rate: float = 1.5) -> str:
			raise AssertionError("schema generation invoked the function")

		details = self.describe(operation)
		schema = details["input_schema"]
		self.assertEqual(schema["required"], ["name", "count"])
		self.assertFalse(schema["additionalProperties"])
		self.assertEqual(schema["properties"]["count"], {"anyOf": [{"type": "integer"}, {"type": "null"}]})
		self.assertEqual(schema["properties"]["enabled"], {"type": "boolean", "default": False})
		self.assertEqual(schema["properties"]["rate"]["default"], 1.5)
		self.assertEqual(details["output_schema"]["type"], "string")
		self.assertEqual(details["schema_errors"], ())
		json.dumps(details, allow_nan=False)

	def test_nested_lists_string_keyed_dictionaries_and_any(self):
		def operation(items: list[dict[str, int]], value: Any) -> dict[str, list[str]]:
			return {}

		details = self.describe(operation)
		self.assertEqual(details["input_schema"]["properties"]["items"], {
			"type": "array", "items": {"type": "object", "additionalProperties": {"type": "integer"}},
		})
		self.assertEqual(details["input_schema"]["properties"]["value"], {})
		self.assertEqual(details["output_schema"]["additionalProperties"], {"type": "array", "items": {"type": "string"}})

	def test_enum_and_literal_values_and_enum_defaults(self):
		def operation(mode: Literal["fast", "slow"], color: Color = Color.RED) -> Color:
			return color

		details = self.describe(operation)
		self.assertEqual(details["input_schema"]["properties"]["mode"], {"enum": ["fast", "slow"]})
		self.assertEqual(details["input_schema"]["properties"]["color"], {"enum": ["red", "blue"], "default": "red"})

	def test_injected_target_is_omitted_even_without_a_binding(self):
		def operation(target: object, value: int) -> int:
			return value

		moves = Moves()
		moves.learn(operation, bind_target=True)
		definition = moves.describe("operation")
		self.assertFalse(definition.available)
		self.assertNotIn("target", definition.signature)
		self.assertEqual(list(definition.input_schema["properties"]), ["value"])

	def test_bound_methods_and_callable_objects_have_effective_schemas(self):
		class Client:
			def get(self, path: str) -> str:
				return path

		class AsyncCallable:
			async def __call__(self, amount: int) -> int:
				return amount

		self.assertEqual(self.describe(Client().get)["input_schema"]["required"], ["path"])
		self.assertEqual(self.describe(AsyncCallable())["input_schema"]["required"], ["amount"])

	def test_positional_only_variadic_and_untyped_inputs_remain_python_usable(self):
		def positional(value: int, /) -> int:
			return value

		def variadic(*values: int) -> int:
			return sum(values)

		def untyped(value) -> str:
			return str(value)

		for func, arguments in ((positional, (1,)), (variadic, (1, 2)), (untyped, (1,))):
			with self.subTest(func=func.__name__):
				moves = Moves()
				moves.learn(func)
				definition = moves.describe(func.__name__)
				self.assertIsNone(definition.input_schema)
				self.assertTrue(definition.schema_errors)
				self.assertIsNotNone(definition.output_schema)
				self.assertEqual(moves.resolve(func.__name__)(*arguments), func(*arguments))

	def test_missing_output_annotation_does_not_remove_valid_inputs(self):
		def operation(value: str):
			return value

		details = self.describe(operation)
		self.assertIsNotNone(details["input_schema"])
		self.assertIsNone(details["output_schema"])
		self.assertIn("Missing return", details["schema_errors"][0])

	def test_non_json_defaults_and_non_string_mapping_keys_are_diagnostic(self):
		def default(value: Any = object()) -> None:
			pass

		def keys(value: dict[int, str]) -> None:
			pass

		for func in (default, keys):
			with self.subTest(func=func.__name__):
				details = self.describe(func)
				self.assertIsNone(details["input_schema"])
				self.assertTrue(details["schema_errors"])

	def test_unresolved_forward_annotations_are_reported(self):
		def operation(value: MissingType) -> str:
			return str(value)

		details = self.describe(operation)
		self.assertIsNone(details["input_schema"])
		self.assertTrue(any("could not be resolved" in error for error in details["schema_errors"]))
		self.assertIsNone(details["output_schema"])

	def test_explicit_schemas_are_copied_and_keep_untyped_functions_simple(self):
		def operation(value):
			return value

		input_schema = {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False}
		moves = Moves()
		moves.learn(operation, input_schema=input_schema, output_schema={"type": "string"})
		input_schema["properties"]["value"]["type"] = "integer"
		definition = moves.describe("operation")
		self.assertEqual(definition.input_schema["properties"]["value"]["type"], "string")
		self.assertEqual(definition.schema_errors, ())
		self.assertEqual(moves.operation("hello"), "hello")
		with self.assertRaises(ValueError):
			MoveSpec("operation", operation, input_schema={"type": "string"})

	def test_parameterless_functions_have_closed_empty_object_inputs(self):
		def operation() -> None:
			pass

		details = self.describe(operation)
		self.assertEqual(details["input_schema"]["properties"], {})
		self.assertEqual(details["input_schema"]["required"], [])
		self.assertFalse(details["input_schema"]["additionalProperties"])
		self.assertEqual(details["output_schema"]["type"], "null")
