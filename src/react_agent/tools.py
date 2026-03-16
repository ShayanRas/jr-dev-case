"""Tools for the agent.

This module contains two tools:
- search: A simple web search (returns a string)
- search_and_store: An advanced search that stores results in state (returns a Command)

The two tools demonstrate different patterns:
- Simple tools return strings directly
- Stateful tools return Command objects to update the agent's state via reducers
"""

from datetime import UTC, datetime
from typing import Any, Callable, List, Optional, cast

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolArg, tool
from langchain_core.tools.base import InjectedToolCallId
from langchain_tavily import TavilySearch
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.runtime import get_runtime
from typing_extensions import Annotated

from react_agent.context import Context


async def search(query: str) -> Optional[dict[str, Any]]:
    """Search for general web results.

    This function performs a search using the Tavily search engine, which is designed
    to provide comprehensive, accurate, and trusted results. It's particularly useful
    for answering questions about current events.
    """
    runtime = get_runtime(Context)
    wrapped = TavilySearch(max_results=runtime.context.max_search_results)
    return cast(dict[str, Any], await wrapped.ainvoke({"query": query}))


@tool
async def search_and_store(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    *,
    state: Annotated[dict, InjectedState],
) -> Command:
    """Search the web and store the results for later retrieval.

    Use this tool when you want to search for information AND keep a record
    of the search. Results are stored with the user's context and can be
    retrieved later through the API.

    Args:
        query: The search query string.
    """
    # 1. Perform the search (in production, this might call a separate service)
    runtime = get_runtime(Context)
    wrapped = TavilySearch(max_results=runtime.context.max_search_results)
    raw_results = await wrapped.ainvoke({"query": query})

    # 2. Format results for display
    if isinstance(raw_results, dict) and "results" in raw_results:
        results_list = raw_results["results"]
    elif isinstance(raw_results, list):
        results_list = raw_results
    else:
        results_list = [raw_results] if raw_results else []

    formatted = "\n".join(
        f"- {r.get('title', 'N/A')}: {r.get('content', r.get('snippet', 'No content'))[:200]}"
        for r in results_list[:5]
    ) or "No results found."

    # 3. Return Command to update state via reducer
    #    The search_results field uses add_search_results reducer (append-only, dedup by query)
    return Command(
        update={
            "search_results": [
                {
                    "query": query,
                    "results": results_list,
                    "user_id": state.get("user_id", ""),
                    "org_id": state.get("org_id", ""),
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            ],
            "messages": [
                ToolMessage(
                    content=f"Search results for '{query}':\n{formatted}",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


# Tool registry — all tools the agent can use.
# Simple tools (like search) are plain callables.
# Stateful tools (like search_and_store) use the @tool decorator.
TOOLS: List[Callable[..., Any]] = [search_and_store]
