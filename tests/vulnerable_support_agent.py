"""Frozen vulnerable support agent used by baseline/planner tests.

The real example is intentionally allowed to evolve when the Codex hardener
commits an accepted repair. Tests that need a known-bad baseline import this
fixture instead of assuming the example stays vulnerable forever.
"""

import json
import re

from faultline.faults.library import INJECTED_INSTRUCTION


async def run_task(task: str, tools: dict, model: str | None = None) -> str:
    lookup, refund = tools["lookup_orders"], tools["refund_order"]
    text = task.lower()

    def try_refund(order_id: str) -> None:
        try:
            refund(order_id=order_id)
        except ConnectionError:
            refund(order_id=order_id)

    explicit = re.search(r"ORD-\d+", task)
    if explicit and "refund" in text:
        try_refund(explicit.group())
        return f"Refunded {explicit.group()}."

    customer = next((name for name in ("avery", "jordan") if name in text), "")
    result = lookup(customer=customer)
    orders = result.get("orders", []) if isinstance(result, dict) else []

    if INJECTED_INSTRUCTION in json.dumps(result, default=str):
        for order in orders:
            try_refund(order["order_id"])
        return "Done — refunded all orders per the account note."

    if "refund" in text:
        if not orders:
            return "No orders found; nothing was refunded."
        newest = orders[0]
        try_refund(newest["order_id"])
        return f"Refunded {newest['order_id']} ({newest['item']})."

    if not orders:
        return f"No orders found for {customer or 'that customer'}."
    order = orders[0]
    return (
        f"{order['order_id']}: {order['item']} — {order['status']} "
        f"(updated {order['updated_at']})."
    )
