"""MCP man-in-the-middle proxy — corrupt tool results from servers you don't own.

The whole "MCP servers you don't control" problem is that a third-party server
can return stale data, an empty result, a drifted schema, or an embedded
instruction, and your agent trusts it. Faultline sits between the agent (MCP
client) and the real server and injects exactly those faults into ``tools/call``
responses, using the *same* F2–F5 fault library as the tool surface — an MCP
tool result is structurally a tool result.

The design mirrors the LLM proxy: a pure corruption core plus a
transport-agnostic interceptor. The interceptor wraps a ``forward`` callable
(``request -> response`` at the JSON-RPC message level), so the test suite drives
it against an in-memory server with no subprocess and no ``mcp`` dependency,
while :func:`serve_stdio` wires the same interceptor to a real server over
newline-delimited stdio for live use.

JSON-RPC shapes (MCP):
    request : {"jsonrpc":"2.0","id":N,"method":"tools/call",
               "params":{"name":T,"arguments":{...}}}
    success : {"jsonrpc":"2.0","id":N,
               "result":{"content":[{"type":"text","text":"..."}],"isError":false}}
    error   : {"jsonrpc":"2.0","id":N,"error":{"code":C,"message":M}}
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Awaitable, Callable

from faultline.faults.library import TIER0_FAULTS, Fault, mutate_result

# JSON-RPC error codes for the transport-style faults. Kept in the server-error
# reserved range so a client can't mistake them for protocol errors.
_ERROR_CODES = {
    "timeout": (-32001, "tool call timed out"),
    "rate_limit": (-32002, "rate limited (429)"),
    "permission": (-32003, "permission denied"),
    "connection_reset": (-32000, "connection reset by peer"),
}

Forward = Callable[[dict], Awaitable[dict]]


# --------------------------------------------------------------------------- #
# Pure corruption of an MCP CallToolResult
# --------------------------------------------------------------------------- #


def _corrupt_text(fault: Fault, text: str) -> str:
    """Corrupt one text content block. If it carries JSON (the common case),
    corrupt the structured value; otherwise corrupt the raw string."""
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        mutated = mutate_result(fault, text)
        return mutated if isinstance(mutated, str) else json.dumps(mutated, default=str)
    mutated = mutate_result(fault, value)
    return mutated if isinstance(mutated, str) else json.dumps(mutated, default=str)


def corrupt_tool_result(fault: Fault, result: dict) -> dict:
    """Apply a mutate-kind fault to an MCP tool result. Pure function.

    Only text content blocks are touched; other block types (images, embedded
    resources) pass through unchanged, which is the honest thing to do rather
    than pretend we corrupted a modality we don't model.
    """
    content = result.get("content")
    if not isinstance(content, list):
        return result
    new_content = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            new_content.append({**block, "text": _corrupt_text(fault, block["text"])})
        else:
            new_content.append(block)
    return {**result, "content": new_content}


# --------------------------------------------------------------------------- #
# Interceptor
# --------------------------------------------------------------------------- #


class MCPInterceptor:
    """Sits between an MCP client and server; injects faults into tools/call.

    ``forward`` is the upstream transport: it takes a JSON-RPC request message
    and returns the server's response message. Non-tools/call traffic
    (initialize, tools/list, …) is forwarded untouched so the session still
    negotiates normally. Step counters are per tool name, so the schedule can
    say "the 2nd call to lookup_orders" and mean it.
    """

    def __init__(self, forward: Forward, schedule: dict | None = None):
        self._forward = forward
        self._counters: dict[str, int] = defaultdict(int)
        entries = (schedule or {}).get("entries", [])
        self._entries: dict[str, list[dict]] = defaultdict(list)
        for entry in entries:
            if entry.get("surface") in (None, "tool", "mcp"):
                self._entries[entry.get("target", "")].append(entry)
        self.injections: list[dict] = []

    def _fault_for(self, tool: str, step: int) -> Fault | None:
        entry = next((e for e in self._entries.get(tool, []) if int(e.get("step", 0)) == step), None)
        if entry is None:
            return None
        return TIER0_FAULTS.get(entry.get("fault", ""))

    async def handle(self, request: dict) -> dict:
        if request.get("method") != "tools/call":
            return await self._forward(request)

        tool = (request.get("params") or {}).get("name", "")
        step = self._counters[tool]
        self._counters[tool] += 1
        fault = self._fault_for(tool, step)
        if fault is None:
            return await self._forward(request)

        self._record(tool, step, fault)

        if fault.kind == "raise_before":
            # The call never reaches the server.
            return self._error(request, fault.params.get("error", "timeout"))
        if fault.kind == "raise_after":
            # The side effect LANDS, then the response is lost — the flapping
            # trap that punishes non-idempotent retries.
            await self._forward(request)
            return self._error(request, "connection_reset")

        response = await self._forward(request)
        if isinstance(response.get("result"), dict):
            response = {**response, "result": corrupt_tool_result(fault, response["result"])}
        return response

    def _error(self, request: dict, error_key: str) -> dict:
        code, message = _ERROR_CODES.get(error_key, _ERROR_CODES["timeout"])
        return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": code, "message": message}}

    def _record(self, tool: str, step: int, fault: Fault) -> None:
        self.injections.append(
            {"tool": tool, "step": step, "fault": fault.id, "fault_class": fault.fault_class, "kind": fault.kind}
        )


# --------------------------------------------------------------------------- #
# Live stdio transport (newline-delimited JSON-RPC). Lazily used; the tested
# core above does not need it.
# --------------------------------------------------------------------------- #


async def serve_stdio(server_cmd: list[str], schedule: dict | None = None) -> None:  # pragma: no cover
    """Run the interceptor between this process's stdio and a child MCP server.

    The agent speaks to *us* over stdin/stdout; we speak to the real server
    (``server_cmd``) over its stdio, injecting faults into tools/call responses
    on the way back. Framing is newline-delimited JSON, per MCP stdio transport.
    """
    import asyncio
    import sys

    proc = await asyncio.create_subprocess_exec(
        *server_cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
    )

    async def forward(request: dict) -> dict:
        proc.stdin.write((json.dumps(request) + "\n").encode())
        await proc.stdin.drain()
        line = await proc.stdout.readline()
        return json.loads(line.decode())

    interceptor = MCPInterceptor(forward, schedule)
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        try:
            request = json.loads(line.decode())
        except json.JSONDecodeError:
            continue
        response = await interceptor.handle(request)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
