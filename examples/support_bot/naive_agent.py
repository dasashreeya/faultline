"""Scripted no-LLM support agent — hardened by the accepted Codex loop.

The pre-hardening implementation was deliberately vulnerable to stale reads,
uncertain side-effect retries, and instructions embedded in tool output. The
current implementation is the source produced by the three accepted repairs.
"""

import re
from datetime import datetime

async def run_task(task: str, tools: dict, model: str | None = None) -> str:
    lookup, refund = tools["lookup_orders"], tools["refund_order"]
    t = task.lower()

    def try_refund(order_id: str) -> bool:
        try:
            result = refund(order_id=order_id)
        except (ConnectionError, TimeoutError):
            # A failed response does not prove a destructive call failed. Without
            # an idempotency key or status lookup, retrying could issue it twice.
            return False
        return isinstance(result, dict) and result.get("refunded") == order_id

    explicit = re.search(r"ORD-\d+", task)
    if explicit and "refund" in t:
        if not try_refund(explicit.group()):
            return "The refund outcome could not be confirmed; no retry was attempted."
        return f"Refunded {explicit.group()}."

    customer = next((c for c in ("avery", "jordan") if c in t), "")
    result = lookup(customer=customer)
    orders = result.get("orders", []) if isinstance(result, dict) else []

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
        if not try_refund(newest["order_id"]):
            return "The refund outcome could not be confirmed; no retry was attempted."
        return f"Refunded {newest['order_id']} ({newest['item']})."

    if not orders:
        return f"No orders found for {customer or 'that customer'}."
    o = orders[0]
    return f"{o['order_id']}: {o['item']} — {o['status']} (updated {o['updated_at']})."
