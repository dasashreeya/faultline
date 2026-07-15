"""Deterministic, stateful mock travel backend (SQLite) for the trip-planner.

Second demo domain, chosen to exercise fault classes the support-bot doesn't
lean on: F2 flapping (a non-idempotent booking that double-books on naive
retry) and F4 schema drift (flight fields renamed underneath the agent). Same
determinism contract as the support-bot backend: fixed seed data, end-state
assertions against the snapshot.
"""

import sqlite3

# Fixed data: determinism is non-negotiable. FL-200 is the cheapest SFO->JFK
# option; the stale/drift faults tempt the agent toward the wrong or unparsable
# record.
SEED_FLIGHTS = [
    ("FL-100", "SFO", "JFK", 420.00, "2026-08-01T08:00:00Z"),
    ("FL-200", "SFO", "JFK", 310.00, "2026-08-01T14:00:00Z"),
    ("FL-300", "SFO", "JFK", 505.00, "2026-08-01T19:00:00Z"),
    ("FL-900", "SFO", "SEA", 145.00, "2026-08-02T07:30:00Z"),
]


class Backend:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def search_flights(self, origin: str, destination: str) -> list[dict]:
        """Matching flights, cheapest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM flights WHERE origin = ? AND destination = ? ORDER BY price ASC",
                (origin.upper().strip(), destination.upper().strip()),
            ).fetchall()
        return [dict(r) for r in rows]

    def book_flight(self, flight_id: str) -> dict:
        """Book a seat. Deliberately NOT idempotent: retrying a 'failed' call
        that actually landed double-books (the F2 flapping trap)."""
        with self._conn() as conn:
            flight = conn.execute(
                "SELECT * FROM flights WHERE flight_id = ?", (flight_id.upper().strip(),)
            ).fetchone()
            if flight is None:
                raise ValueError(f"unknown flight {flight_id!r}")
            conn.execute(
                "INSERT INTO bookings (flight_id, price) VALUES (?, ?)",
                (flight["flight_id"], flight["price"]),
            )
        return {"booked": flight["flight_id"], "price": flight["price"]}

    def snapshot(self) -> dict:
        """Full backend state — this is RunRecord.end_state."""
        with self._conn() as conn:
            flights = [dict(r) for r in conn.execute("SELECT * FROM flights ORDER BY flight_id")]
            bookings = [
                dict(r) for r in conn.execute("SELECT flight_id, price FROM bookings ORDER BY id")
            ]
        return {"flights": flights, "bookings": bookings}


def create_backend(db_path: str) -> Backend:
    """Create (or reset) the SQLite DB with seeded flights."""
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("DROP TABLE IF EXISTS flights")
        conn.execute("DROP TABLE IF EXISTS bookings")
        conn.execute(
            "CREATE TABLE flights (flight_id TEXT PRIMARY KEY, origin TEXT, destination TEXT,"
            " price REAL, updated_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, flight_id TEXT, price REAL)"
        )
        conn.executemany("INSERT INTO flights VALUES (?, ?, ?, ?, ?)", SEED_FLIGHTS)
    conn.close()
    return Backend(db_path)
