"""Raw tools for the trip-planner. Faultline wraps these (intercept/adapters)
before the agent ever sees them — fault injection happens below the agent."""

from examples.trip_planner.backend import Backend, create_backend


def reset_backend(db_path: str) -> None:
    """Fresh, seeded backend before every run — determinism, always."""
    create_backend(db_path)


def snapshot(db_path: str) -> dict:
    return Backend(db_path).snapshot()


def build_tools(db_path: str) -> dict:
    backend = Backend(db_path)

    def search_flights(origin: str, destination: str) -> dict:
        """Search flights between two airports, cheapest first."""
        return {"flights": backend.search_flights(origin, destination)}

    def book_flight(flight_id: str) -> dict:
        """Book a flight by id. Returns the booked fare."""
        return backend.book_flight(flight_id)

    return {"search_flights": search_flights, "book_flight": book_flight}
