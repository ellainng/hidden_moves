"""An optional MCP consumer of the neutral capability catalog."""

from .server import MCPAdapter, serve_stdio

__all__ = ["MCPAdapter", "serve_stdio"]
