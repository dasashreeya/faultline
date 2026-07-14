"""Raw tools for the support-bot. Faultline wraps these (intercept/adapters)
before the agent ever sees them — fault injection happens below the agent."""

from examples.support_bot.backend import Backend, create_backend


def reset_backend(db_path: str) -> None:
    """Fresh, seeded backend before every run — determinism, always."""
    create_backend(db_path)


def snapshot(db_path: str) -> dict:
    return Backend(db_path).snapshot()


def build_tools(db_path: str) -> dict:
    backend = Backend(db_path)

    def lookup_orders(customer: str) -> dict:
        """Look up all orders for a customer, newest first."""
        return {"orders": backend.lookup_orders(customer)}

    def refund_order(order_id: str) -> dict:
        """Refund an order by order id. Returns the refunded amount."""
        return backend.refund_order(order_id)

    return {"lookup_orders": lookup_orders, "refund_order": refund_order}
