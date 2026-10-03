"""Different capabilities exercise the same small composition model."""

import io
import json
import os
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

from hidden_moves import Moves
from hidden_moves.builtins import builtin_registry
from hidden_moves.connectors.json_api import JsonApiClient
from hidden_moves.kit.cmd import run
from hidden_moves.kit.text import slugify
from hidden_moves.notes.obsidian import export_index


class CapabilityTests(unittest.TestCase):
	def test_standalone_text_helper_and_registered_move_agree(self):
		moves = Moves(registry=builtin_registry())
		for value, expected in (("Héllo, World!", "hello-world"), ("---", ""), ("A  B", "a-b")):
			with self.subTest(value=value):
				self.assertEqual(slugify(value), expected)
				self.assertEqual(moves.text.slugify(value), expected)

	def test_builtin_json_move_binds_the_current_target(self):
		moves = Moves({"message": "hello"}, registry=builtin_registry())
		self.assertEqual(json.loads(moves.io.json.dumps(indent=2)), moves.target)

	def test_command_helper_preserves_arguments_and_nonzero_result(self):
		argument = "literal $HOME; --unchanged"
		result = run(
			sys.executable,
			[
				"-c",
				"import sys; print(sys.argv[1]); sys.exit(7)",
				argument,
			],
			capture_output=True,
		)
		self.assertEqual(result.returncode, 7)
		self.assertEqual(result.stdout.strip(), argument)

	def test_obsidian_export_preserves_names_encodes_links_and_keeps_cwd(self):
		class Links(HTMLParser):
			def __init__(self):
				super().__init__()
				self.hrefs = []

			def handle_starttag(self, tag, attrs):
				if tag == "a":
					self.hrefs.append(dict(attrs)["href"])

		cwd = os.getcwd()
		with tempfile.TemporaryDirectory() as temporary:
			vault = Path(temporary)
			(vault / "A.b & C.md").write_text("note", encoding="utf-8")
			(vault / "<script>.md").write_text("note", encoding="utf-8")
			(vault / "directory.md").mkdir()
			output = export_index(vault, vault_name="My Vault & Notes")
			html = output.read_text(encoding="utf-8")
			parser = Links()
			parser.feed(html)
			queries = [parse_qs(urlsplit(href).query) for href in parser.hrefs]
			self.assertEqual(len(queries), 2)
			self.assertIn({"vault": ["My Vault & Notes"], "file": ["A.b & C"]}, queries)
			self.assertIn("&lt;script&gt;", html)
			self.assertTrue(html.endswith("</html>\n"))
		self.assertEqual(os.getcwd(), cwd)


class ConfiguredClientTests(unittest.TestCase):
	def test_configured_bound_method_does_no_work_until_invoked(self):
		requests = []
		responses = []

		def opener(request, *, timeout):
			requests.append((request, timeout))
			response = io.BytesIO(b'{"items": [1, 2]}')
			responses.append(response)
			return response

		moves = Moves(context={"api": {"base_url": "https://example.test/v1/", "timeout": 3.0}})
		client = JsonApiClient(**moves.context["api"], headers={"X-Profile": "demo"}, opener=opener)
		moves.learn(client.get, namespace="api")
		moves.explain("api.get")
		self.assertEqual(requests, [])
		self.assertEqual(moves.api.get("/items", params={"q": "a b"}), {"items": [1, 2]})
		request, timeout = requests[0]
		self.assertEqual(request.full_url, "https://example.test/v1/items?q=a+b")
		self.assertEqual(request.get_header("Accept"), "application/json")
		self.assertEqual(request.get_header("X-profile"), "demo")
		self.assertEqual(timeout, 3.0)
		self.assertTrue(responses[0].closed)

	def test_clients_keep_their_settings_separate(self):
		urls = []

		def opener(request, *, timeout):
			urls.append(request.full_url)
			return io.BytesIO(b"null")

		for base_url in ("https://first.test/", "https://second.test/"):
			moves = Moves()
			moves.learn(JsonApiClient(base_url, opener=opener).get, namespace="api")
			moves.api.get("items")
		self.assertEqual(urls, ["https://first.test/items", "https://second.test/items"])

	def test_bad_configuration_and_absolute_routes_fail_before_network_work(self):
		for timeout in (0, -1, float("inf"), float("nan")):
			with self.subTest(timeout=timeout), self.assertRaises(ValueError):
				JsonApiClient("https://example.test/", timeout=timeout)
		with self.assertRaises(ValueError):
			JsonApiClient("file:///tmp/data")
		client = JsonApiClient("https://example.test/")
		for path in ("https://other.test/data", "//other.test/data", "items#fragment"):
			with self.subTest(path=path), self.assertRaises(ValueError):
				client.get(path)

	def test_transport_errors_propagate_without_silent_fallback(self):
		def opener(request, *, timeout):
			raise URLError("unavailable")

		client = JsonApiClient("https://example.test/", opener=opener)
		with self.assertRaises(URLError):
			client.get("items")
