"""SQLite ledger: every run, score, and patch attempt — accepted or discarded.
The discarded attempts stay; honesty in the report is a feature."""

import json
import sqlite3
from pathlib import Path


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        with self._conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, scenario_id TEXT,"
                " seed INT, attempt INT, record TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS scores (attempt INT PRIMARY KEY, rs REAL,"
                " ts TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS patches (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " attempt INT, scenario_id TEXT, accepted INT, reason TEXT, summary TEXT,"
                " ts TEXT DEFAULT CURRENT_TIMESTAMP)"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def clear_attempt(self, attempt: int) -> None:
        """Drop any prior runs for this attempt.

        run_id is a fresh uuid per run, so re-running the same attempt would
        otherwise append a second full set of rows instead of replacing the
        first. That matters: the harden loop re-runs the gauntlet per attempt,
        and mixing pre-patch runs with post-patch runs would corrupt both the
        dossiers and the survival curve. An attempt is a complete re-run, so
        the previous rows for it are stale by definition.
        """
        with self._conn() as conn:
            conn.execute("DELETE FROM runs WHERE attempt = ?", (attempt,))

    def add_run(self, record: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?)",
                (
                    record["run_id"],
                    record["scenario_id"],
                    record["seed"],
                    record["attempt"],
                    json.dumps(record, default=str),
                ),
            )

    def runs_for_attempt(self, attempt: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT record FROM runs WHERE attempt = ?", (attempt,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def add_score(self, attempt: int, rs: float) -> None:
        with self._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO scores (attempt, rs) VALUES (?, ?)", (attempt, rs))

    def scores(self) -> list[tuple[int, float]]:
        with self._conn() as conn:
            return conn.execute("SELECT attempt, rs FROM scores ORDER BY attempt").fetchall()

    def add_patch(self, attempt: int, scenario_id: str, accepted: bool, reason: str, summary: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO patches (attempt, scenario_id, accepted, reason, summary) VALUES (?, ?, ?, ?, ?)",
                (attempt, scenario_id, int(accepted), reason, summary),
            )

    def patches(self) -> list[dict]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM patches ORDER BY id")]
