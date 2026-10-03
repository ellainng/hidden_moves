"""Discovery reads metadata; provider activation is explicit and atomic."""

import unittest
from importlib.metadata import EntryPoint
from unittest.mock import patch

from hidden_moves import (
	ENTRY_POINT_GROUP,
	MoveSpec,
	ProviderLoadError,
	Registry,
	discover_providers,
	load_provider,
)


class DiscoveryTests(unittest.TestCase):
	def setUp(self):
		self.entry = EntryPoint("example", "example.integration:provide", ENTRY_POINT_GROUP)

	def test_discovery_sorts_metadata_without_importing_providers(self):
		other = EntryPoint("another", "another:provide", ENTRY_POINT_GROUP)
		with (
			patch("hidden_moves.core.discovery.entry_points", return_value=[self.entry, other]) as find,
			patch.object(EntryPoint, "load") as load,
		):
			self.assertEqual(discover_providers(), (other, self.entry))
			find.assert_called_once_with(group=ENTRY_POINT_GROUP)
			load.assert_not_called()

	def test_explicit_loading_records_provider_provenance(self):
		registry = Registry()
		with patch.object(EntryPoint, "load", return_value=lambda: (MoveSpec("upper", str.upper),)):
			loaded = load_provider(self.entry, registry)
		self.assertEqual(loaded[0].source, "example.integration:provide")
		self.assertEqual(registry.resolve("upper").func("hello"), "HELLO")

	def test_missing_optional_dependency_leaves_other_moves_usable(self):
		registry = Registry()
		registry.register(MoveSpec("upper", str.upper))
		with (
			patch.object(EntryPoint, "load", side_effect=ModuleNotFoundError("optional_package")),
			self.assertRaisesRegex(ProviderLoadError, "optional_package"),
		):
			load_provider(self.entry, registry)
		self.assertEqual(registry.resolve("upper").func("hello"), "HELLO")

	def test_provider_collision_does_not_register_earlier_moves(self):
		registry = Registry()
		original = MoveSpec("upper", str.upper)
		registry.register(original)
		with (
			patch.object(EntryPoint, "load", return_value=lambda: (
				MoveSpec("lower", str.lower),
				MoveSpec("upper", str.upper),
			)),
			self.assertRaises(ProviderLoadError),
		):
			load_provider(self.entry, registry)
		self.assertEqual(registry.specs(), (original,))

	def test_failed_provider_generator_does_not_register_partial_results(self):
		def provider():
			yield MoveSpec("upper", str.upper)
			raise RuntimeError("configuration unavailable")

		registry = Registry()
		with (
			patch.object(EntryPoint, "load", return_value=provider),
			self.assertRaisesRegex(ProviderLoadError, "configuration unavailable"),
		):
			load_provider(self.entry, registry)
		self.assertEqual(registry.specs(), ())

	def test_invalid_provider_results_are_actionable(self):
		for provider in (object(), lambda: ("not a MoveSpec",)):
			with self.subTest(provider=provider):
				registry = Registry()
				with (
					patch.object(EntryPoint, "load", return_value=provider),
					self.assertRaises(ProviderLoadError),
				):
					load_provider(self.entry, registry)
				self.assertEqual(registry.specs(), ())
