"""LangGraph / LangChain tool adapter — the breadth signal.

Fault injection is framework-agnostic: it happens *below* the agent, by wrapping
the raw tool callables. So this adapter reuses the exact same
:func:`wrap_tools` core as the OpenAI Agents adapter — the injection semantics
must not differ by framework — and adds one thing LangGraph needs: turning the
wrapped callables into LangChain ``StructuredTool`` objects a graph can bind.

The wrapper preserves each tool's original signature (via ``functools.wraps``'
``__wrapped__``), so LangChain builds a correct args schema even though the
wrapper itself is variadic. LangChain is an optional, lazily-imported dependency:
the offline gauntlet drives ``naive_agent`` through ``wrap_tools`` directly and
never needs it.
"""

from __future__ import annotations

from typing import Callable

# Re-exported so a target repo integrates against one adapter module. The
# injection core lives with the OpenAI adapter because that is where it was
# first defined; both frameworks share it verbatim.
from faultline.intercept.adapters.openai_agents import Transcript, wrap_tools

__all__ = ["Transcript", "wrap_tools", "wrap_langgraph_tools", "to_langchain_tools"]


def wrap_langgraph_tools(
    tools: dict[str, Callable], schedule: dict, transcript: Transcript
) -> dict[str, Callable]:
    """Fault-inject a LangGraph target's tools. Identical semantics to every
    other surface — kept as a named entry point so the integration reads
    clearly in a LangGraph codebase."""
    return wrap_tools(tools, schedule, transcript)


def to_langchain_tools(wrapped: dict[str, Callable]) -> list:
    """Convert fault-wrapped callables into LangChain StructuredTools.

    Requires ``langchain-core``. Raises a clear, actionable error otherwise
    rather than an opaque ImportError deep in a graph build.
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "Binding tools into a LangGraph agent needs langchain-core. Install it "
            "with 'uv pip install langchain-core langgraph langchain-openai'."
        ) from exc

    tools = []
    for name, fn in wrapped.items():
        tools.append(
            StructuredTool.from_function(
                func=fn,
                name=name,
                description=(fn.__doc__ or name).strip().splitlines()[0],
            )
        )
    return tools
