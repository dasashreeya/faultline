# Raw-MCP research agent

This third example speaks raw MCP-shaped JSON-RPC through Faultline's
`MCPInterceptor`. It uses a deterministic SQLite research server with a read
tool (`search_sources`) and a stateful write tool (`save_finding`). No model,
network, API key, or MCP SDK dependency is required.

The intentionally naive agent trusts the server's result ordering. With no
fault it saves the current `SRC-2026` filing; an MCP `stale_data` fault rewrites
the response to a plausible old source and the agent silently saves `SRC-2024`.

```bash
make demo-mcp

# Or compare clean and faulted runs directly:
uv run python -m examples.mcp_research.demo --fault none
uv run python -m examples.mcp_research.demo --fault stale_data
```

Unlike the normal Python-tool examples, requests and responses cross the proxy
as JSON-RPC messages. `src/faultline/intercept/mcp_proxy.py::serve_stdio` uses
the same interceptor core for real newline-delimited MCP server subprocesses.
