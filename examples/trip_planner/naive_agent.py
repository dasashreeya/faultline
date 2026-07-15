"""Scripted no-LLM trip-planner agent — the offline sandbox mode for the second
example. Deliberately naive in the ways a real LangGraph tool node is naive:

- trusts the returned flight ordering, freshness, and field names blindly;
- retries a failed booking without an idempotency key (double-books on flap);
- picks ``flights[0]`` as "cheapest" without re-validating.

`faultline harden` (Codex) is meant to grow the armor — freshness/schema
validators, an idempotency guard on booking — not us.
"""

import re


async def run_task(task: str, tools: dict, model: str | None = None) -> str:
    search, book = tools["search_flights"], tools["book_flight"]
    t = task.lower()

    codes = re.findall(r"\b[A-Z]{3}\b", task)
    origin, destination = (codes + ["SFO", "JFK"])[:2]

    result = search(origin=origin, destination=destination)
    flights = result.get("flights", []) if isinstance(result, dict) else []

    wants_booking = "book" in t or "cheapest" in t
    if not wants_booking:
        if not flights:
            return f"No flights found from {origin} to {destination}."
        options = ", ".join(str(f.get("flight_id", "?")) for f in flights)
        return f"Flights {origin}->{destination}: {options}."

    if not flights:
        return "No flights found; nothing booked."

    cheapest = flights[0]  # trusts returned ordering blindly
    flight_id = cheapest["flight_id"]  # KeyError under schema drift — a loud failure

    def try_book(fid: str) -> None:
        try:
            book(flight_id=fid)
        except ConnectionError:
            book(flight_id=fid)  # naive retry: the first call may have landed

    try_book(flight_id)
    return f"Booked {flight_id} for ${cheapest.get('price', '?')}."
