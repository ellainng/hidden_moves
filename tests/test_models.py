"""Structured schemas are exercised through actual Python model invocation."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import NotRequired, Required, TypedDict

from hidden_moves import Moves
from hidden_moves.adapters import CapabilityArgumentError, CapabilityCatalog

_factory_calls = []


def tag_factory():
	_factory_calls.append("called")
	return ["default"]


@dataclass(frozen=True)
class Address:
	city: str
	postal_code: str | None = None


@dataclass(frozen=True)
class Person:
	name: str
	address: Address
	tags: list[str] = field(default_factory=tag_factory)


@dataclass
class Report:
	count: int
	computed: int = field(init=False)

	def __post_init__(self):
		self.computed = self.count * 2


class Request(TypedDict, total=False):
	name: Required[str]
	address: Address
	labels: NotRequired[list[str]]


@dataclass
class Tree:
	children: list["Tree"] = field(default_factory=list)


class Node(TypedDict):
	child: "Node | None"


@dataclass
class Custom:
	value: str

	def __init__(self, text: str):
		self.value = text


class ModelTests(unittest.TestCase):
	def catalog(self, func):
		moves = Moves()
		moves.learn(func, name="operation")
		return CapabilityCatalog(moves, ["operation"])

	def test_nested_dataclasses_are_constructed_and_results_are_serialized(self):
		def operation(person: Person) -> Person:
			self.assertIsInstance(person, Person)
			self.assertIsInstance(person.address, Address)
			return person

		catalog = self.catalog(operation)
		result = catalog.invoke("operation", {"person": {"name": "Ella", "address": {"city": "Oakland"}, "tags": ["notes"]}})
		self.assertEqual(result, Person("Ella", Address("Oakland"), ["notes"]))
		self.assertEqual(catalog.serialize_result("operation", result), {
			"name": "Ella", "address": {"city": "Oakland", "postal_code": None}, "tags": ["notes"],
		})

	def test_default_factories_run_only_when_constructing_valid_inputs(self):
		_factory_calls.clear()
		calls = []

		def operation(person: Person) -> Person:
			calls.append(person)
			return person

		catalog = self.catalog(operation)
		self.assertEqual(_factory_calls, [])
		for person in ({"name": "Ella", "address": {"city": 1}}, {"address": {"city": "Oakland"}}):
			with self.assertRaises(CapabilityArgumentError):
				catalog.invoke("operation", {"person": person})
		self.assertEqual(calls, [])
		self.assertEqual(_factory_calls, [])
		result = catalog.invoke("operation", {"person": {"name": "Ella", "address": {"city": "Oakland"}}})
		self.assertEqual(result.tags, ["default"])
		self.assertEqual(_factory_calls, ["called"])

	def test_init_false_fields_are_output_only(self):
		def operation(report: Report) -> Report:
			return report

		catalog = self.catalog(operation)
		definition = catalog.describe("operation")
		self.assertEqual(list(definition.input_schema["properties"]["report"]["properties"]), ["count"])
		self.assertEqual(set(definition.output_schema["properties"]), {"count", "computed"})
		with self.assertRaises(CapabilityArgumentError):
			catalog.invoke("operation", {"report": {"count": 2, "computed": 99}})
		result = catalog.invoke("operation", {"report": {"count": 2}})
		self.assertEqual(catalog.serialize_result("operation", result), {"count": 2, "computed": 4})

	def test_typed_dict_required_optional_and_nested_model_fields(self):
		def operation(request: Request) -> Request:
			self.assertIsInstance(request["address"], Address)
			return request

		catalog = self.catalog(operation)
		schema = catalog.describe("operation").input_schema["properties"]["request"]
		self.assertEqual(schema["required"], ("name",))
		with self.assertRaises(CapabilityArgumentError):
			catalog.invoke("operation", {"request": {"address": {"city": "Oakland"}}})
		result = catalog.invoke("operation", {"request": {"name": "Ella", "address": {"city": "Oakland"}}})
		self.assertNotIn("labels", result)
		self.assertEqual(catalog.serialize_result("operation", result)["address"]["city"], "Oakland")

	def test_model_containers_and_optional_unions_are_converted(self):
		def operation(people: list[Person] | None) -> list[Address]:
			return [person.address for person in people] if people else []

		catalog = self.catalog(operation)
		self.assertEqual(catalog.invoke("operation", {"people": None}), [])
		result = catalog.invoke("operation", {"people": [{"name": "Ella", "address": {"city": "Oakland"}, "tags": []}]})
		self.assertEqual(catalog.serialize_result("operation", result), [{"city": "Oakland", "postal_code": None}])

	def test_recursive_models_are_diagnostic_and_direct_python_is_preserved(self):
		for model in (Tree, Node):
			def operation(value):
				return value

			operation.__annotations__ = {"value": model, "return": model}
			moves = Moves()
			moves.learn(operation)
			definition = moves.describe("operation")
			self.assertIsNone(definition.input_schema)
			self.assertTrue(any("Recursive" in error for error in definition.schema_errors))
			value = Tree() if model is Tree else {"child": None}
			self.assertIs(moves.operation(value), value)

	def test_custom_dataclass_constructors_need_a_specialized_input_adapter(self):
		def operation(value: Custom) -> Custom:
			return value

		moves = Moves()
		moves.learn(operation)
		definition = moves.describe("operation")
		self.assertIsNone(definition.input_schema)
		self.assertIsNotNone(definition.output_schema)
		self.assertIsInstance(moves.operation(Custom("hello")), Custom)
