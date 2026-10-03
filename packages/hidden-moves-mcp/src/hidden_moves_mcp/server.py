"""MCP tools consume the neutral catalog without changing its definitions."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Mapping

from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
	INVALID_PARAMS,
	CallToolRequestParams,
	CallToolResult,
	ListToolsResult,
	PaginatedRequestParams,
	TextContent,
	Tool,
	ToolAnnotations,
)

from hidden_moves.adapters import CapabilityArgumentError, CapabilityCatalog, CapabilityResultError

_TOOL_NAME = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
_HINT_NAMES = {
	"read_only": "read_only_hint",
	"destructive": "destructive_hint",
	"idempotent": "idempotent_hint",
	"external": "open_world_hint",
}


class MCPAdapter:
	"""Export and dispatch exactly the catalog's selected capabilities."""

	def __init__(
		self,
		catalog: CapabilityCatalog,
		*,
		tool_names: Mapping[str, str] | None = None,
	) -> None:
		self.catalog = catalog
		aliases = dict(tool_names or {})
		selected = {definition.name for definition in catalog.definitions()}
		if set(aliases) - selected:
			raise ValueError("Tool aliases must reference selected capabilities.")
		self._names = {}
		for definition in catalog.definitions():
			name = aliases.get(definition.name, definition.name)
			if not isinstance(name, str) or not _TOOL_NAME.fullmatch(name):
				raise ValueError("MCP tool names require 1-128 ASCII letters, digits, underscores, hyphens, or dots; supply an alias.")
			if name in self._names:
				raise ValueError(f"MCP tool name collision: {name!r}.")
			self._names[name] = definition.name

	def tools(self) -> list[Tool]:
		tools = []
		for name, qualified_name in self._names.items():
			definition = self.catalog.describe(qualified_name)
			data = definition.to_dict()
			hints = {
				_HINT_NAMES[key]: value for key, value in definition.annotations.to_dict().items()
				if value is not None
			}
			tools.append(Tool(
				name=name,
				description=definition.description,
				input_schema=data["input_schema"],
				output_schema={
					"type": "object",
					"properties": {"result": data["output_schema"] or {}},
					"required": ["result"],
					"additionalProperties": False,
				},
				annotations=ToolAnnotations(**hints) if hints else None,
			))
		return tools

	async def _list_tools(
		self,
		_context: ServerRequestContext,
		params: PaginatedRequestParams | None,
	) -> ListToolsResult:
		if params is not None and params.cursor:
			raise MCPError(code=INVALID_PARAMS, message="This catalog has no pagination cursors.")
		return ListToolsResult(tools=self.tools())

	async def _call_tool(
		self,
		_context: ServerRequestContext,
		params: CallToolRequestParams,
	) -> CallToolResult:
		try:
			qualified_name = self._names[params.name]
		except KeyError as error:
			raise MCPError(code=INVALID_PARAMS, message="Unknown or unexposed tool.") from error
		try:
			result = self.catalog.invoke(qualified_name, params.arguments if params.arguments is not None else {})
			if inspect.isawaitable(result):
				result = await result
			value = self.catalog.serialize_result(qualified_name, result)
		except (CapabilityArgumentError, CapabilityResultError) as error:
			return CallToolResult(is_error=True, content=[TextContent(type="text", text=str(error))])
		except Exception as error:
			# Capability errors may contain private client state; report the failure type.
			return CallToolResult(is_error=True, content=[TextContent(
				type="text", text=f"Capability {params.name!r} failed ({type(error).__name__}).",
			)])
		structured = {"result": value}
		return CallToolResult(
			content=[TextContent(type="text", text=json.dumps(structured, ensure_ascii=False, allow_nan=False))],
			structured_content=structured,
		)

	def server(self, name: str = "hidden-moves", *, version: str = "0.1.0") -> Server:
		return Server(name, version=version, on_list_tools=self._list_tools, on_call_tool=self._call_tool)


async def serve_stdio(server: Server) -> None:
	"""Serve until the host closes stdin; the SDK owns the protocol connection."""
	async with stdio_server() as (read_stream, write_stream):
		await server.run(read_stream, write_stream, server.create_initialization_options())
