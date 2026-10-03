"""Definitions describe ordinary capabilities without executing them."""

import json
import unittest
from dataclasses import FrozenInstanceError
from importlib.metadata import EntryPoint
from unittest.mock import Mock, patch

from hidden_moves import (
	ENTRY_POINT_GROUP,
	MoveAnnotations,
	MoveCollisionError,
	MoveDefinition,
	Moves,
	MoveSpec,
	load_provider,
)


class DefinitionTests(unittest.TestCase):
	def test_definition_preserves_full_documentation_and_explicit_hints(self):
		def search(query: str) -> list[str]:
			"""Search local notes.

			Use this for existing notes in the configured notebook.
			"""
			raise AssertionError("inspection invoked a capability")

		moves = Moves()
		moves.learn(search, namespace="notes", annotations=MoveAnnotations(
			read_only=True, destructive=False, external=False,
		))
		definition = moves.describe("notes.search")
		self.assertIsInstance(definition, MoveDefinition)
		self.assertIn("configured notebook", definition.description)
		self.assertEqual(moves.moves()[0].summary, "Search local notes.")
		self.assertTrue(definition.annotations.read_only)
		self.assertIsNone(definition.annotations.idempotent)
		self.assertFalse(definition.annotations.destructive)
		self.assertEqual(moves.explain("notes.search"), definition.to_dict())
		json.dumps(definition.to_dict(), allow_nan=False)
		self.assertIs(moves.resolve("notes.search"), search)

	def test_metadata_is_copied_deeply_and_export_views_are_independent(self):
		metadata = {"tags": ["notes"], "example": {"query": "hello"}}
		moves = Moves()
		spec = moves.learn(lambda: None, name="search", metadata=metadata)
		metadata["tags"].append("changed")
		metadata["example"]["query"] = "changed"
		with self.assertRaises(TypeError):
			spec.metadata["example"]["query"] = "another"
		definition = moves.describe("search")
		with self.assertRaises(FrozenInstanceError):
			definition.name = "other"
		view = definition.to_dict()
		self.assertEqual(view["metadata"], {"tags": ["notes"], "example": {"query": "hello"}})
		view["metadata"]["tags"].append("export changed")
		self.assertEqual(definition.to_dict()["metadata"]["tags"], ["notes"])

	def test_invalid_metadata_and_hints_fail_at_registration(self):
		for metadata in ({"value": object()}, {1: "value"}, {"value": float("nan")}, []):
			with self.subTest(metadata=type(metadata)), self.assertRaises(TypeError):
				MoveSpec("value", lambda: None, metadata=metadata)
		cycle = {}
		cycle["self"] = cycle
		with self.assertRaisesRegex(ValueError, "circular"):
			MoveSpec("value", lambda: None, metadata=cycle)
		for hints in ({"read_only": 1}, {"destructive": "false"}):
			with self.subTest(hints=hints), self.assertRaises(TypeError):
				MoveAnnotations(**hints)
		with self.assertRaises(TypeError):
			MoveSpec("value", lambda: None, annotations={"read_only": True})

	def test_unknown_hints_are_not_replaced_with_safety_claims(self):
		moves = Moves()
		moves.learn(lambda: None, name="value")
		self.assertEqual(moves.explain("value")["annotations"], {
			"read_only": None, "destructive": None, "idempotent": None, "external": None,
		})

	def test_explicit_description_overrides_docstring(self):
		moves = Moves()
		moves.learn(str.upper, name="upper", description="Custom description.\nMore detail.")
		self.assertEqual(moves.describe("upper").description, "Custom description.\nMore detail.")

	def test_bound_definitions_do_not_expose_target_or_context(self):
		def write(target, path: str) -> str:
			return path

		moves = Moves("target-secret", context={"token": "context-secret"})
		moves.learn(write, bind_target=True)
		definition = moves.describe("write")
		self.assertTrue(definition.available)
		self.assertNotIn("target", definition.signature)
		self.assertNotIn("secret", json.dumps(definition.to_dict()))
		unbound = Moves(registry=moves.registry).describe("write")
		self.assertFalse(unbound.available)
		self.assertIn("requires", unbound.binding_error)

	def test_bound_methods_and_async_callable_objects_are_inspectable(self):
		class Client:
			def get(self, path: str) -> str:
				raise AssertionError("inspection invoked a method")

		class AsyncClient:
			async def __call__(self, path: str) -> str:
				return path

		moves = Moves()
		moves.learn(Client().get, namespace="api")
		moves.learn(AsyncClient(), name="get", namespace="async_api")
		self.assertNotIn("self", moves.describe("api.get").signature)
		self.assertTrue(moves.describe("async_api.get").is_async)

	def test_opaque_signature_does_not_break_description(self):
		moves = Moves()
		func = Mock()
		moves.learn(func, name="opaque")
		with patch("hidden_moves.core.moves.inspect.signature", side_effect=ValueError):
			self.assertIsNone(moves.describe("opaque").signature)
		func.assert_not_called()

	def test_provider_loading_preserves_annotations_and_metadata(self):
		entry = EntryPoint("example", "example:provide", ENTRY_POINT_GROUP)
		spec = MoveSpec("upper", str.upper, annotations=MoveAnnotations(read_only=True), metadata={"tag": "text"})
		moves = Moves()
		with patch.object(EntryPoint, "load", return_value=lambda: [spec]):
			load_provider(entry, moves.registry)
		definition = moves.describe("upper")
		self.assertEqual(definition.source, "example:provide")
		self.assertEqual(definition.metadata["tag"], "text")
		self.assertTrue(definition.annotations.read_only)

	def test_describe_name_is_reserved_at_the_container_root(self):
		with self.assertRaises(MoveCollisionError):
			Moves().learn(lambda: None, name="describe")
