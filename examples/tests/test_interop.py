"""The installed demonstration must preserve behavior across every consumer."""

import json
import subprocess
import sys
import unittest
from pathlib import Path


class InteroperabilityTests(unittest.TestCase):
	def test_one_installed_function_has_matching_consumer_results(self):
		demo = Path(__file__).resolve().parents[1] / "interop_demo.py"
		process = subprocess.run([sys.executable, str(demo)], capture_output=True, text=True, timeout=30)
		self.assertEqual(process.returncode, 0, process.stderr)
		data = json.loads(process.stdout)
		self.assertEqual(data["results"], {
			"direct_python": "hello/hello/hello",
			"registry_python": "hello/hello/hello",
			"cli": "hello/hello/hello",
			"mcp": "hello/hello/hello",
			"function_tool": "hello/hello/hello",
		})
		definition = data["definition"]
		self.assertEqual(definition["name"], "example.text.repeat")
		self.assertTrue(definition["available"])
		self.assertEqual(definition["schema_errors"], [])
		self.assertEqual(data["mcp_tool"]["inputSchema"], definition["input_schema"])
		self.assertEqual(data["mcp_protocol_version"], "2026-07-28")
		self.assertEqual(data["function_tool"]["name"], "example__text__repeat")
		self.assertIs(data["function_tool"]["strict"], False)
		self.assertEqual(data["function_tool"]["parameters"]["required"], ["value"])
		self.assertEqual(data["function_output"]["type"], "function_call_output")
