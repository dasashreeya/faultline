"""One-command raw-MCP demo driven through Faultline's interceptor."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from faultline.intercept.mcp_proxy import MCPInterceptor

from .agent import RawMCPResearchAgent
from .server import ResearchMCPServer


async def run_demo(fault: str | None = "stale_data") -> dict:
    with tempfile.TemporaryDirectory(prefix="faultline-mcp-research-") as temp_dir:
        server = ResearchMCPServer(Path(temp_dir) / "research.sqlite3")
        entries = []
        if fault:
            entries.append(
                {
                    "step": 0,
                    "surface": "mcp",
                    "target": "search_sources",
                    "fault": fault,
                }
            )
        schedule = {"scenario_id": "MCP-stale-01", "seed": 1, "entries": entries}
        interceptor = MCPInterceptor(server.handle, schedule)
        answer = await RawMCPResearchAgent(interceptor.handle).run(
            "Research Acme revenue and save the newest supported finding."
        )
        return {
            "answer": answer,
            "end_state": server.snapshot(),
            "injections": interceptor.injections,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fault", default="stale_data", choices=["stale_data", "empty_result", "none"]
    )
    args = parser.parse_args()
    result = asyncio.run(run_demo(None if args.fault == "none" else args.fault))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
