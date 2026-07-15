"""Integration tests for the MCP man-in-the-middle proxy.

The interceptor wraps a ``forward`` callable, so an in-memory JSON-RPC server
stands in for a real MCP server — no subprocess, no ``mcp`` dependency. These
tests prove the proxy corrupts tools/call results with the shared fault library
and gets the transport-fault semantics (short-circuit vs land-then-drop) right.
"""

import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.faults.library import INJECTED_INSTRUCTION, STALE_TIMESTAMP  # noqa: E402
from faultline.intercept.mcp_proxy import MCPInterceptor, corrupt_tool_result  # noqa: E402


class InMemoryMCPServer:
    """A minimal MCP server: dispatches tools/call, tracks side effects."""

    def __init__(self):
        self.refunds: list[str] = []
        self.tool_calls = 0

    async def forward(self, request: dict) -> dict:
        method = request.get("method")
        rid = request.get("id")
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "lookup_orders"}]}}
        if method != "tools/call":
            return {"jsonrpc": "2.0", "id": rid, "result": {}}

        self.tool_calls += 1
        params = request.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "lookup_orders":
            payload = {
                "orders": [
                    {"order_id": "ORD-1002", "item": "monitor", "updated_at": "2026-07-10T09:30:00Z"},
                    {"order_id": "ORD-1001", "item": "keyboard", "updated_at": "2026-06-01T10:00:00Z"},
                ]
            }
        elif name == "refund_order":
            self.refunds.append(args.get("order_id", "?"))
            payload = {"refunded": args.get("order_id")}
        else:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "unknown tool"}}
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": False},
        }


def _schedule(*entries):
    return {
        "scenario_id": "mcp-test",
        "seed": 1,
        "entries": [
            {"step": step, "surface": "mcp", "target": tool, "fault": fault}
            for step, tool, fault in entries
        ],
    }


def _call(tool, **arguments):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}


def _text(response: dict) -> str:
    return response["result"]["content"][0]["text"]


# --------------------------------------------------------------------------- #


def test_passthrough_when_no_fault():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=None)
    resp = asyncio.run(proxy.handle(_call("lookup_orders")))
    assert "ORD-1002" in _text(resp)
    assert proxy.injections == []


def test_stale_data_rewrites_the_timestamp():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((0, "lookup_orders", "stale_data")))
    resp = asyncio.run(proxy.handle(_call("lookup_orders")))
    payload = json.loads(_text(resp))
    assert payload["orders"][0]["updated_at"] == STALE_TIMESTAMP
    assert proxy.injections[0]["fault"] == "stale_data"


def test_empty_result_blanks_the_payload():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((0, "lookup_orders", "empty_result")))
    resp = asyncio.run(proxy.handle(_call("lookup_orders")))
    assert json.loads(_text(resp)) == {"orders": []}


def test_injected_instruction_appears_in_result():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((0, "lookup_orders", "injected_instruction")))
    resp = asyncio.run(proxy.handle(_call("lookup_orders")))
    assert INJECTED_INSTRUCTION in _text(resp)


def test_malformed_json_breaks_parseability():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((0, "lookup_orders", "malformed_json")))
    resp = asyncio.run(proxy.handle(_call("lookup_orders")))
    import pytest

    with pytest.raises(json.JSONDecodeError):
        json.loads(_text(resp))


def test_schema_drift_camelcases_keys():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((0, "lookup_orders", "schema_drift")))
    resp = asyncio.run(proxy.handle(_call("lookup_orders")))
    payload = json.loads(_text(resp))
    assert "orderId" in payload["orders"][0]
    assert "order_id" not in payload["orders"][0]


def test_timeout_short_circuits_before_the_server():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((0, "refund_order", "tool_timeout")))
    resp = asyncio.run(proxy.handle(_call("refund_order", order_id="ORD-1003")))
    assert resp["error"]["code"] == -32001
    assert server.tool_calls == 0  # never forwarded
    assert server.refunds == []


def test_flapping_lands_the_side_effect_then_drops_the_response():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((0, "refund_order", "tool_flapping")))
    resp = asyncio.run(proxy.handle(_call("refund_order", order_id="ORD-1003")))
    assert resp["error"]["code"] == -32000
    # the refund LANDED even though the client sees an error — the trap
    assert server.refunds == ["ORD-1003"]


def test_non_tool_traffic_passes_through():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((0, "lookup_orders", "empty_result")))
    resp = asyncio.run(proxy.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/list"}))
    assert resp["result"]["tools"][0]["name"] == "lookup_orders"
    assert proxy.injections == []  # tools/list must not consume a fault


def test_step_targeting_hits_the_right_call():
    server = InMemoryMCPServer()
    proxy = MCPInterceptor(server.forward, schedule=_schedule((1, "lookup_orders", "empty_result")))
    first = asyncio.run(proxy.handle(_call("lookup_orders")))
    second = asyncio.run(proxy.handle(_call("lookup_orders")))
    assert "ORD-1002" in _text(first)  # step 0 untouched
    assert json.loads(_text(second)) == {"orders": []}  # step 1 faulted


def test_corrupt_tool_result_leaves_non_text_blocks_alone():
    from faultline.faults.library import TIER0_FAULTS

    result = {"content": [{"type": "image", "data": "..."}, {"type": "text", "text": "{}"}], "isError": False}
    out = corrupt_tool_result(TIER0_FAULTS["injected_instruction"], result)
    assert out["content"][0] == {"type": "image", "data": "..."}  # untouched
    assert INJECTED_INSTRUCTION in out["content"][1]["text"]


def test_determinism_same_schedule_same_injections():
    def run():
        server = InMemoryMCPServer()
        proxy = MCPInterceptor(
            server.forward,
            schedule=_schedule((0, "lookup_orders", "stale_data"), (1, "lookup_orders", "empty_result")),
        )
        for _ in range(2):
            asyncio.run(proxy.handle(_call("lookup_orders")))
        return [i["fault"] for i in proxy.injections]

    assert run() == run() == ["stale_data", "empty_result"]
