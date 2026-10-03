"""Selection, validation, and invocation at the neutral consumer boundary."""

import asyncio
import inspect
import unittest
from enum import Enum

from hidden_moves import Moves, UnknownMoveError
from hidden_moves.adapters import (
	CapabilityArgumentError,
	CapabilityCatalog,
	CapabilityExposureError,
	CapabilityResultError,
)


class Mode(Enum):
	FIRST = "first"
	SECOND = "second"


class CatalogTests(unittest.TestCase):
	def test_selection_limits_both_discovery_and_invocation(self):
		def first(value: str) -> str:
			return value

		def second() -> str:
			raise AssertionError("unselected operation was called")

		moves = Moves()
		moves.learn(first)
		moves.learn(second)
		catalog = CapabilityCatalog(moves, ["first"])
		self.assertEqual([item.name for item in catalog.definitions()], ["first"])
		self.assertEqual(catalog.invoke("first", {"value": "hello"}), "hello")
		for method in (catalog.describe, lambda name: catalog.invoke(name, {})):
			with self.assertRaises(UnknownMoveError):
				method("second")

	def test_bad_arguments_fail_before_side_effects(self):
		calls = []

		def operation(count: int, names: list[str], *, enabled: bool = False) -> int:
			calls.append((count, names, enabled))
			return count

		moves = Moves()
		moves.learn(operation)
		catalog = CapabilityCatalog(moves, ["operation"])
		for arguments in (
			{}, {"count": True, "names": []}, {"count": "1", "names": []},
			{"count": 1, "names": [2]}, {"count": 1, "names": [], "extra": 2},
			{"count": 1, "names": [], "enabled": 1}, [], {"count": float("nan"), "names": []},
		):
			with self.subTest(arguments=arguments), self.assertRaises(CapabilityArgumentError):
				catalog.invoke("operation", arguments)
		self.assertEqual(calls, [])
		self.assertEqual(catalog.invoke("operation", {"count": 2.0, "names": ["hello"]}), 2)
		self.assertIs(type(calls[0][0]), int)

	def test_enum_conversion_preserves_the_ordinary_python_function(self):
		def operation(mode: Mode, others: list[Mode] | None = None) -> Mode:
			self.assertIsInstance(mode, Mode)
			self.assertIsInstance(others[0], Mode)
			return mode

		moves = Moves()
		moves.learn(operation)
		catalog = CapabilityCatalog(moves, ["operation"])
		result = catalog.invoke("operation", {"mode": "first", "others": ["second"]})
		self.assertIs(result, Mode.FIRST)
		self.assertEqual(catalog.serialize_result("operation", result), "first")

	def test_catalog_snapshots_match_definitions_to_the_original_callables(self):
		def first(value: str) -> str:
			return "first:" + value

		def replacement(value: int) -> int:
			return value

		moves = Moves()
		moves.learn(first, name="operation")
		catalog = CapabilityCatalog(moves, ["operation"])
		moves.learn(replacement, name="operation", replace=True)
		self.assertEqual(catalog.invoke("operation", {"value": "hello"}), "first:hello")
		self.assertEqual(catalog.describe("operation").input_schema["properties"]["value"]["type"], "string")

	def test_bound_clients_and_targets_are_ready_before_exposure(self):
		def add(target: int, value: int) -> int:
			return target + value

		moves = Moves(4)
		moves.learn(add, bind_target=True, target_types=(int,))
		catalog = CapabilityCatalog(moves, ["add"])
		self.assertEqual(catalog.invoke("add", {"value": 2}), 6)
		with self.assertRaises(CapabilityExposureError):
			CapabilityCatalog(Moves(registry=moves.registry), ["add"])

	def test_unsupported_schema_keywords_are_rejected_at_exposure(self):
		moves = Moves()
		moves.learn(lambda value: value, name="operation", input_schema={
			"type": "object", "properties": {"value": {"type": "integer", "minimum": 1}},
		})
		with self.assertRaisesRegex(CapabilityExposureError, "minimum"):
			CapabilityCatalog(moves, ["operation"])
		self.assertEqual(moves.operation(0), 0)

	def test_explicit_schema_defaults_do_not_replace_python_defaults(self):
		def operation(value="python"):
			return value

		moves = Moves()
		moves.learn(operation, input_schema={"type": "object", "properties": {"value": {"type": "string", "default": "schema"}}, "additionalProperties": False})
		catalog = CapabilityCatalog(moves, ["operation"])
		self.assertEqual(catalog.invoke("operation", {}), "python")

	def test_python_argument_binding_is_checked_before_invocation(self):
		calls = []

		def operation(value):
			calls.append(value)

		moves = Moves()
		moves.learn(operation, input_schema={"type": "object"})
		catalog = CapabilityCatalog(moves, ["operation"])
		with self.assertRaises(CapabilityArgumentError):
			catalog.invoke("operation", {"unknown": 1})
		self.assertEqual(calls, [])

	def test_capability_errors_propagate_and_result_errors_are_separate(self):
		def failure() -> str:
			raise RuntimeError("capability failure")

		def wrong() -> int:
			return "wrong type"

		moves = Moves()
		moves.learn(failure)
		moves.learn(wrong)
		catalog = CapabilityCatalog(moves, ["wrong", "failure"])
		with self.assertRaisesRegex(RuntimeError, "capability failure"):
			catalog.invoke("failure", {})
		result = catalog.invoke("wrong", {})
		self.assertEqual(result, "wrong type")
		with self.assertRaises(CapabilityResultError):
			catalog.serialize_result("wrong", result)
		with self.assertRaises(CapabilityResultError):
			catalog.serialize_result("wrong", object())

	def test_selection_is_sorted_and_duplicate_names_are_deduplicated(self):
		moves = Moves()
		for name in ("second", "first"):
			moves.learn(lambda: None, name=name, input_schema={"type": "object"})
		catalog = CapabilityCatalog(moves, ["second", "first", "second"])
		self.assertEqual([item.name for item in catalog.definitions()], ["first", "second"])
		self.assertEqual(CapabilityCatalog(moves, []).definitions(), ())
		with self.assertRaises(TypeError):
			CapabilityCatalog(moves, "first")


class AsyncCatalogTests(unittest.IsolatedAsyncioTestCase):
	async def test_async_results_and_sync_returned_awaitables_pass_through(self):
		async def asynchronous(value: int) -> int:
			return value + 1

		def wrapped(value: int) -> int:
			return asynchronous(value)

		moves = Moves()
		moves.learn(asynchronous)
		moves.learn(wrapped)
		catalog = CapabilityCatalog(moves, ["asynchronous", "wrapped"])
		for name in ("asynchronous", "wrapped"):
			result = catalog.invoke(name, {"value": 2})
			self.assertTrue(inspect.isawaitable(result))
			self.assertEqual(await result, 3)

	async def test_cancellation_is_not_swallowed(self):
		async def operation() -> None:
			raise asyncio.CancelledError

		moves = Moves()
		moves.learn(operation)
		catalog = CapabilityCatalog(moves, ["operation"])
		with self.assertRaises(asyncio.CancelledError):
			await catalog.invoke("operation", {})
