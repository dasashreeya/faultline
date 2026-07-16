"""Raw-MCP research example: end-to-end JSON-RPC through the interceptor."""

import asyncio

from examples.mcp_research.demo import run_demo


def test_clean_raw_mcp_agent_saves_newest_source():
    result = asyncio.run(run_demo(None))

    assert result["end_state"]["findings"] == [
        {"source_id": "SRC-2026", "claim": "Acme revenue grew 18% year over year."}
    ]
    assert result["injections"] == []


def test_stale_mcp_result_causes_silent_wrong_finding():
    result = asyncio.run(run_demo("stale_data"))

    assert result["end_state"]["findings"] == [
        {"source_id": "SRC-2024", "claim": "Acme revenue grew 3% year over year."}
    ]
    assert result["injections"][0] == {
        "tool": "search_sources",
        "step": 0,
        "fault": "stale_data",
        "fault_class": "F3",
        "kind": "mutate",
    }


def test_empty_mcp_result_fails_safely_without_side_effect():
    result = asyncio.run(run_demo("empty_result"))

    assert result["answer"] == "No sources found; nothing saved."
    assert result["end_state"]["findings"] == []
