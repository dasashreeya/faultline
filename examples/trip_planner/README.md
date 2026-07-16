# trip-planner (second example — a different domain, different faults)

A booking agent — search flights, book the cheapest — over a deterministic
SQLite backend. It is the breadth signal: a second domain that leans on fault
classes the support-bot doesn't, and proves Faultline is framework-agnostic.

Two agents, same wrapped tools:

- `naive_agent.py` — scripted, no LLM. The **default**, fully offline path.
- `agent.py` — a **LangGraph** ReAct agent (optional extras: `langgraph`,
  `langchain-openai`, `OPENAI_API_KEY`). Fault injection is identical because it
  happens below the framework, via `intercept/adapters/langgraph.py`.

## Run it (offline, no API key)

```bash
uv run faultline break --path examples/trip_planner
uv run faultline report --path examples/trip_planner
```

## What breaks, and why

| Scenario    | Fault          | Naive outcome                                             |
| ----------- | -------------- | -------------------------------------------------------- |
| TP-flap-01  | tool_flapping  | **D** — retry double-books; the customer is charged twice |
| TP-stale-04 | stale_data     | **D** — books a pricier stale flight, reports success     |
| TP-drift-02 | schema_drift   | **B** — camelCased fields crash the parser (loud)         |
| TP-empty-03 | empty_result   | **A** — no flights, nothing booked (honest)               |

Baseline Resilience Score: **35.0/100**. The flapping double-book is this
domain's crown-jewel silent failure — the analogue of the support-bot's stale
refund.

## To run the live LangGraph agent

```bash
uv sync --extra langgraph
export OPENAI_API_KEY=...
# then set target.agent to examples.trip_planner.agent:run_task in faultline.yaml
```
