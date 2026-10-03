"""CLI parsing and errors at the thin adapter boundary."""

import json
import subprocess
import sys
import unittest
from importlib.metadata import EntryPoint
from unittest.mock import patch

from click.testing import CliRunner

from hidden_moves import ENTRY_POINT_GROUP, MoveSpec
from hidden_moves.cli import main


class CliTests(unittest.TestCase):
	def setUp(self):
		self.runner = CliRunner()

	def test_help_and_move_listing_do_not_discover_or_execute_providers(self):
		with patch("hidden_moves.cli.discover_providers") as discover:
			for arguments in (["--help"], ["moves", "list"]):
				result = self.runner.invoke(main, arguments)
				self.assertEqual(result.exit_code, 0, result.output)
			discover.assert_not_called()
		self.assertIn("io.json.dumps", result.output)

	def test_json_and_text_commands_invoke_the_registered_capabilities(self):
		result = self.runner.invoke(main, ["text", "slugify", "Héllo, World!"])
		self.assertEqual(result.exit_code, 0, result.output)
		self.assertEqual(result.output.strip(), "hello-world")
		result = self.runner.invoke(main, ["json", "dumps", '{"value": 1}', "--indent", "2"])
		self.assertEqual(result.exit_code, 0, result.output)
		self.assertEqual(json.loads(result.output), {"value": 1})

	def test_invalid_json_and_unknown_moves_have_useful_errors(self):
		result = self.runner.invoke(main, ["json", "dumps", "{broken"])
		self.assertEqual(result.exit_code, 2)
		self.assertIn("Invalid value", result.output)
		result = self.runner.invoke(main, ["moves", "show", "unknown"])
		self.assertEqual(result.exit_code, 1)
		self.assertIn("Unknown move", result.output)

	def test_show_reports_a_target_requirement_without_invocation(self):
		result = self.runner.invoke(main, ["moves", "show", "io.json.dumps"])
		self.assertEqual(result.exit_code, 0, result.output)
		details = json.loads(result.output)
		self.assertFalse(details["available"])
		self.assertTrue(details["bind_target"])

	def test_json_listing_reports_schemas_without_invocation(self):
		def operation(value: str) -> str:
			raise AssertionError("listing executed a capability")

		entry = EntryPoint("example", "example:provide", ENTRY_POINT_GROUP)
		with (
			patch("hidden_moves.cli.discover_providers", return_value=(entry,)),
			patch.object(EntryPoint, "load", return_value=lambda: (MoveSpec("operation", operation),)),
		):
			result = self.runner.invoke(main, ["--plugin", "example", "moves", "list", "--json"])
		self.assertEqual(result.exit_code, 0, result.output)
		definitions = json.loads(result.output)
		self.assertEqual([item["name"] for item in definitions], sorted(item["name"] for item in definitions))
		definition = next(item for item in definitions if item["name"] == "operation")
		self.assertEqual(definition["input_schema"]["required"], ["value"])

	def test_generic_call_uses_the_catalog_and_returns_json(self):
		result = self.runner.invoke(main, ["moves", "call", "text.slugify", "--arguments", '{"value": "Hello World"}'])
		self.assertEqual(result.exit_code, 0, result.output)
		self.assertEqual(json.loads(result.output), "hello-world")

	def test_bad_json_and_invalid_arguments_fail_before_execution(self):
		def operation(value: str) -> str:
			raise AssertionError("invalid arguments executed")

		entry = EntryPoint("example", "example:provide", ENTRY_POINT_GROUP)
		with (
			patch("hidden_moves.cli.discover_providers", return_value=(entry,)),
			patch.object(EntryPoint, "load", return_value=lambda: (MoveSpec("operation", operation),)),
		):
			for arguments in ("{broken", "[]", "{}", '{"value": 1}', '{"value": "ok", "extra": 1}'):
				with self.subTest(arguments=arguments):
					result = self.runner.invoke(main, ["--plugin", "example", "moves", "call", "operation", "--arguments", arguments])
					self.assertNotEqual(result.exit_code, 0)
					self.assertNotIn("invalid arguments executed", result.output)

	def test_generic_call_reports_missing_binding(self):
		result = self.runner.invoke(main, ["moves", "call", "io.json.dumps"])
		self.assertEqual(result.exit_code, 1)
		self.assertIn("requires Moves", result.output)

	def test_generic_call_awaits_async_providers_in_the_cli(self):
		async def add(value: int) -> int:
			return value + 1

		entry = EntryPoint("example", "example:provide", ENTRY_POINT_GROUP)
		with (
			patch("hidden_moves.cli.discover_providers", return_value=(entry,)),
			patch.object(EntryPoint, "load", return_value=lambda: (MoveSpec("add", add),)),
		):
			result = self.runner.invoke(main, ["--plugin", "example", "moves", "call", "add", "--arguments", '{"value": 2}'])
		self.assertEqual(result.exit_code, 0, result.output)
		self.assertEqual(json.loads(result.output), 3)

	def test_capability_failure_has_a_terminal_error(self):
		def failure() -> None:
			raise RuntimeError("example failure")

		entry = EntryPoint("example", "example:provide", ENTRY_POINT_GROUP)
		with (
			patch("hidden_moves.cli.discover_providers", return_value=(entry,)),
			patch.object(EntryPoint, "load", return_value=lambda: (MoveSpec("failure", failure),)),
		):
			result = self.runner.invoke(main, ["--plugin", "example", "moves", "call", "failure"])
		self.assertEqual(result.exit_code, 1)
		self.assertIn("example failure", result.output)

	def test_system_flags_are_forwarded_and_helpers_are_not_commands(self):
		with patch("hidden_moves.kit.cmd.commands.subprocess.run") as run:
			run.return_value = subprocess.CompletedProcess(["ls"], 0)
			result = self.runner.invoke(main, ["cmd", "run", "ls", "-lahC", "."])
			self.assertEqual(result.exit_code, 0, result.output)
			self.assertEqual(run.call_args.args[0], ["ls", "-lahC", "."])
		self.assertEqual(set(main.commands["cmd"].commands), {"run"})

	def test_system_nonzero_exit_code_reaches_the_cli(self):
		result = self.runner.invoke(main, ["cmd", "run", sys.executable, "-c", "raise SystemExit(7)"])
		self.assertEqual(result.exit_code, 7)

	def test_missing_system_program_has_a_cli_error(self):
		with patch("hidden_moves.kit.cmd.commands.subprocess.run", side_effect=FileNotFoundError("missing")):
			result = self.runner.invoke(main, ["cmd", "run", "missing-program"])
		self.assertEqual(result.exit_code, 1)
		self.assertIn("missing", result.output)

	def test_plugin_listing_reads_metadata_without_loading(self):
		entry = EntryPoint("example", "example:provide", ENTRY_POINT_GROUP)
		with (
			patch("hidden_moves.commands.capabilities.discover_providers", return_value=(entry,)),
			patch.object(EntryPoint, "load") as load,
		):
			result = self.runner.invoke(main, ["plugins", "list"])
		self.assertEqual(result.exit_code, 0, result.output)
		self.assertIn("example:provide", result.output)
		load.assert_not_called()

	def test_explicit_plugin_loading_is_scoped_to_one_invocation(self):
		entry = EntryPoint("example", "example:provide", ENTRY_POINT_GROUP)
		with (
			patch("hidden_moves.cli.discover_providers", return_value=(entry,)),
			patch.object(EntryPoint, "load", return_value=lambda: (MoveSpec("upper", str.upper),)),
		):
			loaded = self.runner.invoke(main, ["--plugin", "example", "moves", "show", "upper"])
			self.assertEqual(loaded.exit_code, 0, loaded.output)
			self.assertEqual(json.loads(loaded.output)["source"], "example:provide")
		unloaded = self.runner.invoke(main, ["moves", "show", "upper"])
		self.assertEqual(unloaded.exit_code, 1)

	def test_missing_and_ambiguous_provider_names_do_not_load_any_package(self):
		entry = EntryPoint("example", "example:provide", ENTRY_POINT_GROUP)
		other = EntryPoint("example", "other:provide", ENTRY_POINT_GROUP)
		for entries in ((), (entry, other)):
			with (
				self.subTest(entries=entries),
				patch("hidden_moves.cli.discover_providers", return_value=entries),
				patch.object(EntryPoint, "load") as load,
			):
				result = self.runner.invoke(main, ["--plugin", "example", "moves", "list"])
				self.assertEqual(result.exit_code, 1)
				load.assert_not_called()
