"""One independently usable function through inspection and multiple consumers."""

import asyncio
import json
import subprocess
import sys

from mcp import Client

from hidden_moves import Moves, discover_providers, load_provider
from hidden_moves.adapters import CapabilityCatalog
from hidden_moves_example_text import repeat_text
from hidden_moves_mcp import MCPAdapter
from hidden_moves_openai import FunctionToolAdapter

CAPABILITY = "example.text.repeat"
ARGUMENTS = {"value": "hello", "count": 3, "separator": "/"}


async def demonstrate() -> dict:
	"""Use the installed provider explicitly, without network or model API calls."""
	providers = [entry for entry in discover_providers() if entry.name == "example-text"]
	if len(providers) != 1:
		raise RuntimeError("Install exactly one example-text provider before running this demonstration.")
	moves = Moves()
	load_provider(providers[0], moves.registry)
	catalog = CapabilityCatalog(moves, [CAPABILITY])
	mcp_adapter = MCPAdapter(catalog)
	function_adapter = FunctionToolAdapter(catalog)

	results = {
		"direct_python": repeat_text(**ARGUMENTS),
		"registry_python": moves.resolve(CAPABILITY)(**ARGUMENTS),
	}
	command = subprocess.run(
		[sys.executable, "-m", "hidden_moves", "--plugin", "example-text", "moves", "call",
		 CAPABILITY, "--arguments", json.dumps(ARGUMENTS)],
		capture_output=True, text=True, check=True, timeout=10,
	)
	results["cli"] = json.loads(command.stdout)
	async with asyncio.timeout(20):
		async with Client(mcp_adapter.server(), read_timeout_seconds=10) as client:
			listing = await client.list_tools()
			if [tool.name for tool in listing.tools] != [CAPABILITY]:
				raise RuntimeError("The MCP catalog exposed an unexpected tool selection.")
			response = await client.call_tool(CAPABILITY, ARGUMENTS)
			if response.is_error:
				raise RuntimeError("The local MCP call failed.")
			results["mcp"] = response.structured_content["result"]
			protocol_version = client.protocol_version
	function_tool, = function_adapter.tools()
	function_output = await function_adapter.call_output("local-call-1", function_tool["name"], json.dumps(ARGUMENTS))
	results["function_tool"] = json.loads(function_output["output"])
	if any(result != results["direct_python"] for result in results.values()):
		raise RuntimeError("The consumer results differ from the ordinary Python function.")
	return {
		"definition": moves.describe(CAPABILITY).to_dict(),
		"mcp_protocol_version": protocol_version,
		"mcp_tool": listing.tools[0].model_dump(by_alias=True, exclude_none=True),
		"function_tool": function_tool,
		"function_output": function_output,
		"results": results,
	}


def main() -> None:
	print(json.dumps(asyncio.run(demonstrate()), ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
	main()
