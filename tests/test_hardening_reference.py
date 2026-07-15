"""Reference behavior for the P0 hardener acceptance target.

This is a test-only repair oracle. It is not installed into the example agent
and does not replace the real Codex hardener; it proves that a general repair
can raise the score against the same deterministic gauntlet.
"""

import asyncio
import shutil
from pathlib import Path

import pytest

from faultline.config import load_config
from faultline.plan.planner import build_plan
from faultline.run.gauntlet import run_gauntlet


REPO = Path(__file__).resolve().parents[1]


async def hardened_reference_agent(task: str, tools: dict, model: str | None = None) -> str:
    """General repair oracle: validate reads, avoid unsafe retries, fail loudly."""
    lookup, refund = tools["lookup_orders"], tools["refund_order"]
    text = task.lower()

    def read_orders(customer: str) -> list[dict]:
        first = lookup(customer=customer)
        second = lookup(customer=customer)
        for result in (second, first):
            orders = result.get("orders") if isinstance(result, dict) else None
            if isinstance(orders, list) and all(isinstance(order, dict) for order in orders):
                return sorted(orders, key=lambda order: str(order.get("updated_at", "")), reverse=True)
        return []

    explicit = next((part for part in task.split() if part.startswith("ORD-")), None)
    if explicit and "refund" in text:
        try:
            refund(order_id=explicit.rstrip(".,"))
        except (ConnectionError, TimeoutError):
            return f"Could not confirm refund for {explicit}."
        return f"Refunded {explicit.rstrip('.,')}."

    customer = next((name for name in ("avery", "jordan") if name in text), "")
    orders = read_orders(customer)
    if "refund" in text:
        if not orders:
            return "No verified orders found; nothing was refunded."
        order_id = orders[0].get("order_id")
        if not order_id:
            return "The order data was incomplete; nothing was refunded."
        try:
            refund(order_id=order_id)
        except (ConnectionError, TimeoutError):
            return f"Could not confirm refund for {order_id}."
        return f"Refunded {order_id}."

    if not orders:
        return f"No verified orders found for {customer or 'that customer'}."
    order = orders[0]
    return f"{order.get('order_id')}: {order.get('item')} — {order.get('status')}"


@pytest.fixture()
def cfg(tmp_path):
    root = tmp_path / "support_bot"
    shutil.copytree(
        REPO / "examples" / "support_bot",
        root,
        ignore=shutil.ignore_patterns(".faultline", "__pycache__"),
    )
    return load_config(root)


def test_reference_repair_improves_the_same_planned_gauntlet(cfg):
    plan = build_plan(cfg, mode="curated")

    cfg.agent_entrypoint = "tests.vulnerable_support_agent:run_task"
    baseline, _ = asyncio.run(run_gauntlet(cfg, attempt=0, plan=plan, persist=False))

    cfg.agent_entrypoint = "tests.test_hardening_reference:hardened_reference_agent"
    repaired, records = asyncio.run(run_gauntlet(cfg, attempt=1, plan=plan, persist=False))

    assert repaired > baseline
    assert repaired >= 85.0
    assert all(record["judge"]["grade"] in {"A", "B"} for record in records)
