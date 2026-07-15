"""Trip-planner: LangGraph agent (the breadth signal, live path).

Intentionally naive in the same ways as the scripted sandbox agent: no
idempotency guard on booking, no freshness or schema validation. `faultline
harden` (Codex) is supposed to grow the armor.

Requires the optional extras: langgraph, langchain-openai, and OPENAI_API_KEY.
The offline sandbox uses naive_agent:run_task instead, so nothing here is on the
default judging path.
"""

INSTRUCTIONS = (
    "You are a travel booking assistant. Use the tools to search flights and "
    "book the requested one. Answer concisely with the outcome."
)


async def run_task(task: str, tools: dict, model: str | None = None) -> str:
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    from faultline.intercept.adapters.langgraph import to_langchain_tools

    # `tools` are already Faultline-wrapped callables; bind them as LangChain
    # StructuredTools so the graph can call them with faults injected below.
    lc_tools = to_langchain_tools(tools)
    # GPT-5.6 exposes function tools through Chat Completions only when
    # reasoning is disabled; LangGraph supplies tools to every model call.
    llm = ChatOpenAI(
        model=model or "gpt-5.6",
        temperature=0,
        reasoning_effort="none",
    )
    agent = create_react_agent(llm, lc_tools)

    result = await agent.ainvoke(
        {"messages": [("system", INSTRUCTIONS), ("user", task)]}
    )
    messages = result.get("messages", [])
    return str(messages[-1].content) if messages else ""
