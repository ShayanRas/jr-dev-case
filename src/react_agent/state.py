"""Define the state structures for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep
from typing_extensions import Annotated


def add_search_results(
    existing: list[dict[str, Any]], new: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Append-only reducer for search results.

    Deduplicates by query string to prevent storing the same search twice
    within a single session. This is a pattern used in production agents
    to accumulate tool outputs in state without unbounded growth.
    """
    existing_queries = {r["query"] for r in existing}
    return existing + [r for r in new if r["query"] not in existing_queries]


@dataclass
class InputState:
    """Input state — the narrower interface exposed to callers.

    When invoking the agent graph, callers pass user_id and org_id
    alongside the messages. This models how the API gateway (Server)
    passes authenticated user context into the agent layer (Hinge).
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    user_id: str = ""
    org_id: str = ""


@dataclass
class State(InputState):
    """Full internal state of the agent.

    Extends InputState with fields that accumulate during the agent's
    execution. Fields with reducer annotations (like search_results)
    are append-only — new values are merged with existing ones rather
    than replacing them.
    """

    search_results: Annotated[
        list[dict[str, Any]], add_search_results
    ] = field(default_factory=list)

    is_last_step: IsLastStep = field(default=False)

    # --- Candidate: add your classifications field here ---
    # Hint: follow the same pattern as search_results above.
    # You'll need to write a reducer function (like add_search_results)
    # and annotate your field with it.
