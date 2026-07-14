"""Deterministic, stateful mock CRM backend (SQLite) for the support-bot.

Seeded orders make end-state assertions trivial and reproducible for judges.
Deliberately fragile in Codex-fixable ways: refunds are not idempotent and
nothing validates freshness — the agent is supposed to grow that armor.
"""

import sqlite3

# Fixed timestamps: determinism is non-negotiable. ORD-1002 is avery's most
# recent order; the stale_data fault tempts the agent toward ORD-1001.
SEED_ORDERS = [
    ("ORD-1001", "avery", "keyboard", 89.00, "delivered", "2026-06-01T10:00:00Z"),
    ("ORD-1002", "avery", "monitor", 349.00, "shipped", "2026-07-10T09:30:00Z"),
    ("ORD-1003", "jordan", "webcam", 59.00, "delivered", "2026-06-20T15:45:00Z"),
]


class Backend:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def lookup_orders(self, customer: str) -> list[dict]:
        """All orders for a customer, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM orders WHERE customer = ? ORDER BY updated_at DESC",
                (customer.lower().strip(),),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_order(self, order_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE order_id = ?", (order_id.upper().strip(),)
            ).fetchone()
        return dict(row) if row else None

    def refund_order(self, order_id: str) -> dict:
        """Issue a refund. Deliberately NOT idempotent: retrying a 'failed'
        call that actually landed double-refunds (the F2 flapping trap)."""
        order = self.get_order(order_id)
        if order is None:
            raise ValueError(f"unknown order {order_id!r}")
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO refunds (order_id, amount) VALUES (?, ?)",
                (order["order_id"], order["amount"]),
            )
        return {"refunded": order["order_id"], "amount": order["amount"]}

    def snapshot(self) -> dict:
        """Full backend state — this is RunRecord.end_state."""
        with self._conn() as conn:
            refunds = [
                dict(r) for r in conn.execute("SELECT order_id, amount FROM refunds ORDER BY id")
            ]
            orders = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY order_id")]
        return {"orders": orders, "refunds": refunds}


def create_backend(db_path: str) -> Backend:
    """Create (or reset) the SQLite DB with seeded orders."""
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute("DROP TABLE IF EXISTS refunds")
        conn.execute(
            "CREATE TABLE orders (order_id TEXT PRIMARY KEY, customer TEXT, item TEXT,"
            " amount REAL, status TEXT, updated_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE refunds (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, amount REAL)"
        )
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", SEED_ORDERS)
    conn.close()
    return Backend(db_path)
