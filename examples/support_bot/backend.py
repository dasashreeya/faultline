"""Deterministic, stateful mock CRM backend (SQLite) for the support-bot.

Seeded orders make end-state assertions trivial and reproducible for judges.
Deliberately fragile in Codex-fixable ways: no timeouts, no freshness checks,
trusts tool output verbatim. Owner: Person A, Day 1.
"""

SEED_ORDERS = [
    {"order_id": "ORD-1001", "customer": "avery", "item": "keyboard", "amount": 89.00, "status": "delivered"},
    {"order_id": "ORD-1002", "customer": "avery", "item": "monitor", "amount": 349.00, "status": "shipped"},
    {"order_id": "ORD-1003", "customer": "jordan", "item": "webcam", "amount": 59.00, "status": "delivered"},
]


def create_backend(db_path: str):
    """Create the SQLite DB, seed orders, return a handle with lookup/refund ops."""
    raise NotImplementedError("tier-0, day 1")


def snapshot(db_path: str) -> dict:
    """Full backend state — this is the RunRecord.end_state the detectors assert on."""
    raise NotImplementedError("tier-0, day 1")
