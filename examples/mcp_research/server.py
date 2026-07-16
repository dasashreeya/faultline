"""Deterministic stateful MCP research server used by the raw-client example."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SOURCES = [
    (
        "SRC-2026",
        "Acme FY2026 filing",
        "Acme revenue grew 18% year over year.",
        "2026-07-12T09:30:00Z",
    ),
    (
        "SRC-2024",
        "Acme archive mirror",
        "Acme revenue grew 3% year over year.",
        "2024-02-01T08:00:00Z",
    ),
]


class ResearchMCPServer:
    """Small JSON-RPC server with one read tool and one stateful write tool."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.reset()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def reset(self) -> None:
        with self._connection() as conn:
            conn.execute("DROP TABLE IF EXISTS sources")
            conn.execute("DROP TABLE IF EXISTS findings")
            conn.execute(
                "CREATE TABLE sources (source_id TEXT PRIMARY KEY, title TEXT, claim TEXT, updated_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE findings (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, claim TEXT)"
            )
            conn.executemany("INSERT INTO sources VALUES (?, ?, ?, ?)", SOURCES)

    async def handle(self, request: dict) -> dict:
        request_id = request.get("id")
        method = request.get("method")
        if method == "initialize":
            return self._ok(
                request_id,
                {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}},
            )
        if method == "tools/list":
            return self._ok(
                request_id,
                {
                    "tools": [
                        {
                            "name": "search_sources",
                            "description": "Find revenue sources, newest first",
                        },
                        {
                            "name": "save_finding",
                            "description": "Save one sourced research finding",
                        },
                    ]
                },
            )
        if method != "tools/call":
            return self._error(request_id, -32601, "method not found")

        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name == "search_sources":
            query = str(arguments.get("query", "")).lower()
            with self._connection() as conn:
                rows = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT * FROM sources ORDER BY updated_at DESC"
                    )
                ]
            if query:
                rows = [
                    row
                    for row in rows
                    if query in (row["title"] + " " + row["claim"]).lower()
                ]
            return self._tool_result(request_id, {"sources": rows})
        if name == "save_finding":
            source_id = str(arguments.get("source_id", ""))
            claim = str(arguments.get("claim", ""))
            with self._connection() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM sources WHERE source_id = ?", (source_id,)
                ).fetchone()
                if not exists:
                    return self._error(request_id, -32602, "unknown source")
                conn.execute(
                    "INSERT INTO findings (source_id, claim) VALUES (?, ?)", (source_id, claim)
                )
            return self._tool_result(request_id, {"saved": source_id})
        return self._error(request_id, -32601, f"unknown tool {name!r}")

    def snapshot(self) -> dict:
        with self._connection() as conn:
            findings = [
                dict(row)
                for row in conn.execute("SELECT source_id, claim FROM findings ORDER BY id")
            ]
        return {"findings": findings}

    @staticmethod
    def _ok(request_id: object, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @classmethod
    def _tool_result(cls, request_id: object, payload: dict) -> dict:
        return cls._ok(
            request_id,
            {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": False},
        )

    @staticmethod
    def _error(request_id: object, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
