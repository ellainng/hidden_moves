"""Behavior at the registration and per-object binding boundaries."""

import inspect
import json
import unittest

from hidden_moves import (
	MoveBindingError,
	MoveCollisionError,
	Moves,
	MoveSpec,
	Registry,
	UnknownMoveError,
)


class RegistryTests(unittest.TestCase):
	def test_collisions_require_explicit_replacement(self):
		moves = Moves()
		moves.learn(lambda: "first", name="value")
		with self.assertRaises(MoveCollisionError):
			moves.learn(lambda: "second", name="value")
		self.assertEqual(moves.value(), "first")
		moves.learn(lambda: "second", name="value", replace=True)
		self.assertEqual(moves.value(), "second")

	def test_move_and_namespace_collisions_in_both_directions(self):
		for first, second in (("io", "io.json"), ("io.json", "io")):
			with self.subTest(first=first):
				registry = Registry()
				for index, path in enumerate((first, second)):
					namespace, _, name = path.rpartition(".")
					spec = MoveSpec(name, lambda: None, namespace=namespace or None)
					if index == 0:
						registry.register(spec)
					else:
						with self.assertRaises(MoveCollisionError):
							registry.register(spec, replace=True)
				self.assertEqual([spec.qualified_name for spec in registry.specs()], [first])

	def test_container_api_names_are_reserved_even_as_namespaces(self):
		for name in ("learn", "target", "registry", "context", "resolve", "moves"):
			with self.subTest(name=name):
				with self.assertRaises(MoveCollisionError):
					Registry().register(MoveSpec("value", lambda: None, namespace=name))
				with self.assertRaises(MoveCollisionError):
					Moves().learn(lambda: None, name=name)

	def test_batch_failure_does_not_publish_partial_registration(self):
		registry = Registry()
		original = MoveSpec("existing", lambda: "original")
		registry.register(original)
		with self.assertRaises(MoveCollisionError):
			registry.register_many((
				MoveSpec("new", lambda: None),
				MoveSpec("existing", lambda: "replacement"),
			))
		self.assertEqual(registry.specs(), (original,))

	def test_names_remain_usable_as_python_attributes(self):
		for name in ("", "with-dash", "class", "_private", "a.b"):
			with self.subTest(name=name), self.assertRaises(ValueError):
				MoveSpec(name, lambda: None)
		with self.assertRaises(ValueError):
			MoveSpec("read", lambda: None, namespace="io..json")


class BindingTests(unittest.TestCase):
	def test_plain_callables_keep_their_original_arguments(self):
		moves = Moves(target="unused")
		moves.learn(str.upper, name="upper", target_types=(str,))
		self.assertIs(moves.upper, str.upper)
		self.assertEqual(moves.upper("hello"), "HELLO")

	def test_json_binding_and_shared_registry_keep_targets_separate(self):
		registry = Registry()
		registry.register(MoveSpec("dumps", json.dumps, namespace="io.json", bind_target=True))
		first_target = {"value": 1}
		second_target = {"value": 2}
		first = Moves(first_target, registry=registry)
		second = Moves(second_target, registry=registry)
		self.assertEqual(json.loads(first.io.json.dumps()), first_target)
		self.assertEqual(json.loads(second.io.json.dumps()), second_target)
		self.assertEqual(json.loads(json.dumps(first_target)), first_target)
		self.assertNotIn("dumps", first_target)
		self.assertFalse(hasattr(dict, "dumps"))

	def test_none_is_a_real_target(self):
		moves = Moves(None)
		moves.learn(json.dumps, bind_target=True)
		self.assertEqual(moves.dumps(), "null")
		self.assertIsNone(moves.target)

	def test_missing_and_incompatible_targets_report_binding_errors(self):
		registry = Registry()
		registry.register(MoveSpec("upper", str.upper, bind_target=True, target_types=(str,)))
		for moves in (Moves(registry=registry), Moves(42, registry=registry)):
			with self.subTest(moves=moves), self.assertRaises(MoveBindingError):
				moves.resolve("upper")
			self.assertFalse(moves.explain("upper")["available"])
			self.assertTrue(moves.knows("upper"))

	def test_namespaces_and_introspection_follow_new_registrations(self):
		moves = Moves()
		moves.learn(str.upper, name="upper", namespace="text")
		namespace = moves.text
		moves.learn(str.lower, name="lower", namespace="text")
		self.assertEqual(namespace.lower("HELLO"), "hello")
		self.assertIn("text", dir(moves))
		self.assertIn("lower", dir(namespace))
		self.assertEqual(
			[spec.qualified_name for spec in moves.moves()],
			["text.lower", "text.upper"],
		)
		self.assertFalse(hasattr(moves, "unknown"))
		with self.assertRaises(UnknownMoveError):
			moves.resolve("unknown")

	def test_bound_signatures_and_provenance_are_visible(self):
		def export(target, destination, *, indent=2):
			return target, destination, indent

		moves = Moves({"value": 1}, context={"secret": "never-display-this"})
		moves.learn(export, bind_target=True, provider="example.exports")
		self.assertEqual(
			list(inspect.signature(moves.export).parameters),
			["destination", "indent"],
		)
		details = moves.explain("export")
		self.assertEqual(details["source"], "example.exports")
		self.assertEqual(details["signature"], "(destination, *, indent=2)")
		self.assertNotIn("never-display-this", str(details))
		self.assertEqual(moves.export("result.json"), ({"value": 1}, "result.json", 2))

	def test_context_is_explicit_and_outer_mapping_is_copied(self):
		configuration = {"profile": "first"}
		moves = Moves(context=configuration)
		configuration["profile"] = "changed"
		self.assertEqual(moves.context["profile"], "first")
		with self.assertRaises(TypeError):
			moves.context["profile"] = "another"
		moves.learn(lambda context: context["profile"], name="profile")
		self.assertEqual(moves.profile(moves.context), "first")
		with self.assertRaises(TypeError):
			moves.profile()

	def test_callable_objects_can_be_learned_with_an_explicit_name(self):
		class Double:
			def __call__(self, value):
				return value * 2

		moves = Moves()
		with self.assertRaisesRegex(ValueError, "name="):
			moves.learn(Double())
		moves.learn(Double(), name="double")
		self.assertEqual(moves.double(3), 6)


class AsyncBindingTests(unittest.IsolatedAsyncioTestCase):
	async def test_async_moves_preserve_await_inside_an_existing_event_loop(self):
		async def add(target, amount):
			return target + amount

		moves = Moves(4)
		moves.learn(add, bind_target=True)
		self.assertTrue(inspect.iscoroutinefunction(moves.add))
		self.assertTrue(moves.explain("add")["is_async"])
		self.assertEqual(await moves.add(3), 7)

	async def test_async_callable_objects_remain_awaitable(self):
		class AsyncDouble:
			async def __call__(self, value):
				return value * 2

		moves = Moves()
		moves.learn(AsyncDouble(), name="double")
		self.assertTrue(moves.explain("double")["is_async"])
		self.assertEqual(await moves.double(3), 6)
