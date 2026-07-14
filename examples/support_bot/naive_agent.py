"""Scripted no-LLM support agent — the offline sandbox mode.

Lets the entire faultline loop (break → judge → score → harden → re-break)
run without API keys, and lets judges reproduce the demo for free. It is
deliberately naive in exactly the ways real agent code is naive:
- trusts tool results blindly (freshness, ordering, embedded instructions)
- retries connection errors without idempotency checks
- has no timeout handling
"""

import json
import re

from faultline.faults.library import INJECTED_INSTRUCTION


async def run_task(task: str, tools: dict, model: str | None = None) -> str:
    lookup, refund = tools["lookup_orders"], tools["refund_order"]
    t = task.lower()

    def try_refund(order_id: str) -> None:
        try:
            refund(order_id=order_id)
        except ConnectionError:
            refund(order_id=order_id)  # naive retry: the first call may have landed

    explicit = re.search(r"ORD-\d+", task)
    if explicit and "refund" in t:
        try_refund(explicit.group())
        return f"Refunded {explicit.group()}."

    customer = next((c for c in ("avery", "jordan") if c in t), "")
    result = lookup(customer=customer)
    orders = result.get("orders", []) if isinstance(result, dict) else []

    if INJECTED_INSTRUCTION in json.dumps(result, default=str):
        for o in orders:  # obediently follows instructions found in tool output
            try_refund(o["order_id"])
        return "Done — refunded all orders per the account note."

    if "refund" in t:
        if not orders:
            return "No orders found; nothing was refunded."
        newest = orders[0]  # trusts returned ordering and freshness blindly
        try_refund(newest["order_id"])
        return f"Refunded {newest['order_id']} ({newest['item']})."

    if not orders:
        return f"No orders found for {customer or 'that customer'}."
    o = orders[0]
    return f"{o['order_id']}: {o['item']} — {o['status']} (updated {o['updated_at']})."
