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
from datetime import datetime

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
        # A latest-order refund is destructive and freshness-sensitive. Confirm it
        # with an independent bounded read, then rank the combined observations
        # ourselves instead of trusting either response's completeness or order.
        confirmation = lookup(customer=customer)
        observations = (result, confirmation)
        validated: dict[str, tuple[dict, datetime]] = {}
        for response in observations:
            response_orders = response.get("orders") if isinstance(response, dict) else None
            if not isinstance(response_orders, list):
                return "Could not verify current order data; no refund was issued."
            for order in response_orders:
                if not isinstance(order, dict) or not all(
                    isinstance(order.get(field), str)
                    for field in ("order_id", "customer", "item", "status", "updated_at")
                ):
                    return "Could not verify current order data; no refund was issued."
                if order["customer"].lower().strip() != customer:
                    return "Could not verify current order data; no refund was issued."
                try:
                    updated_at = datetime.fromisoformat(order["updated_at"].replace("Z", "+00:00"))
                except ValueError:
                    return "Could not verify current order data; no refund was issued."
                previous = validated.get(order["order_id"])
                if previous is None or updated_at > previous[1]:
                    validated[order["order_id"]] = (order, updated_at)
        if not validated:
            return "No orders found; nothing was refunded."
        newest = max(validated.values(), key=lambda entry: entry[1])[0]
        try_refund(newest["order_id"])
        return f"Refunded {newest['order_id']} ({newest['item']})."

    if not orders:
        return f"No orders found for {customer or 'that customer'}."
    o = orders[0]
    return f"{o['order_id']}: {o['item']} — {o['status']} (updated {o['updated_at']})."
