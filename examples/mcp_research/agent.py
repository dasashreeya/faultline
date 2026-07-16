"""Intentionally naive research agent that speaks raw MCP JSON-RPC."""

from __future__ import annotations

import json
from typing import Awaitable, Callable


Transport = Callable[[dict], Awaitable[dict]]


class RawMCPResearchAgent:
    def __init__(self, transport: Transport):
        self.transport = transport
        self._request_id = 0

    async def _call(self, tool: str, **arguments) -> dict:
        self._request_id += 1
        response = await self.transport(
            {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            }
        )
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        text = response["result"]["content"][0]["text"]
        return json.loads(text)

    async def run(self, task: str) -> str:
        # Deliberately trusts the first result and the server's ordering. A
        # stale-data fault therefore produces a plausible, silently wrong save.
        result = await self._call("search_sources", query="acme")
        sources = result.get("sources", [])
        if not sources:
            return "No sources found; nothing saved."
        source = sources[0]
        await self._call(
            "save_finding", source_id=source["source_id"], claim=source["claim"]
        )
        return f"Saved {source['source_id']}: {source['claim']}"
