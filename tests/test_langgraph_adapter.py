"""The LangGraph adapter must inject faults identically to the OpenAI adapter
and expose tool signatures LangChain can build a schema from."""

import inspect
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.intercept.adapters.langgraph import (  # noqa: E402
    Transcript,
    to_langchain_tools,
    wrap_langgraph_tools,
)


def _tools():
    def search_flights(origin: str, destination: str) -> dict:
        """Search flights between two airports."""
        return {"flights": [{"flight_id": "FL-200", "price": 310}]}

    return {"search_flights": search_flights}


def _schedule(fault):
    return {"entries": [{"step": 0, "surface": "tool", "target": "search_flights", "fault": fault}]}


def test_wrapping_preserves_signature_and_doc():
    wrapped = wrap_langgraph_tools(_tools(), _schedule("empty_result"), Transcript())["search_flights"]
    assert str(inspect.signature(wrapped)) == "(origin: str, destination: str) -> dict"
    assert wrapped.__doc__.strip().startswith("Search flights")


def test_wrapping_injects_faults_below_the_framework():
    tr = Transcript()
    wrapped = wrap_langgraph_tools(_tools(), _schedule("empty_result"), tr)["search_flights"]
    assert wrapped(origin="SFO", destination="JFK") == {"flights": []}  # emptied
    assert any(e["type"] == "fault_injected" for e in tr.events)


def test_passthrough_without_a_fault_returns_real_result():
    wrapped = wrap_langgraph_tools(_tools(), {"entries": []}, Transcript())["search_flights"]
    assert wrapped(origin="SFO", destination="JFK")["flights"][0]["flight_id"] == "FL-200"


def test_to_langchain_tools_is_actionable_without_langchain():
    """Either langchain-core is installed and we get real tools, or we get a
    clear install message — never an opaque ImportError."""
    try:
        import langchain_core.tools  # noqa: F401
    except ImportError:
        wrapped = wrap_langgraph_tools(_tools(), {"entries": []}, Transcript())
        with pytest.raises(RuntimeError, match="langchain-core"):
            to_langchain_tools(wrapped)
    else:  # pragma: no cover - only when the optional extra is present
        wrapped = wrap_langgraph_tools(_tools(), {"entries": []}, Transcript())
        tools = to_langchain_tools(wrapped)
        assert tools[0].name == "search_flights"
