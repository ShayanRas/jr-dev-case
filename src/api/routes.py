"""API routes -- the gateway endpoints.

This module follows the proxy pattern: the API layer handles authentication
and validation, then delegates to the agent (Hinge) or database. Business
logic lives in the agent and its tools, not here.

Architecture:
    Frontend -> API (this file) -> Agent (graph.py) -> Tools -> External APIs
                     |
                     +-> Database (for persistence/retrieval)
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import HumanMessage

from api.database import fetch_search_results, store_search_result
from api.schemas import (
    ChatRequest,
    ChatResponse,
    SearchListResponse,
    SearchResult,
)
from react_agent.graph import graph
from react_agent.utils import get_message_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


# --- Chat endpoint ---


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the agent and get a response.

    The API layer:
    1. Validates the request (Pydantic handles this)
    2. Passes user context (user_id, org_id) into the agent's state
    3. Invokes the agent graph
    4. Persists any search results the agent accumulated
    5. Returns the agent's response
    """
    logger.debug(
        "Processing chat for user=%s org=%s model_config=%s",
        request.user_id,
        request.org_id,
        os.environ.get("ANTHROPIC_API_KEY", "not-set"),
    )

    try:
        # Invoke the agent with user context in the input state
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "user_id": request.user_id,
                "org_id": request.org_id,
            },
        )
    except Exception as e:
        logger.error("Agent invocation failed: %s", e)
        raise HTTPException(
            status_code=500, detail="Agent failed to process request"
        )

    # Extract response text from the last message
    response_text = get_message_text(result["messages"][-1])

    # Persist search results that the agent accumulated via reducers
    stored_count = 0
    for sr in result.get("search_results", []):
        try:
            await store_search_result(
                user_id=sr.get("user_id", request.user_id),
                org_id=sr.get("org_id", request.org_id),
                query=sr["query"],
                results=sr.get("results", []),
            )
            stored_count += 1
        except Exception as e:
            logger.error("Failed to persist search result: %s", e)

    return ChatResponse(
        response=response_text, search_results_stored=stored_count
    )


# --- Search history endpoints ---


@router.get("/searches/{user_id}", response_model=SearchListResponse)
async def get_searches(
    user_id: str,
    org_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> SearchListResponse:
    """Retrieve stored search results for a user.

    In production, user_id would come from JWT auth (not the URL path).
    This simplified version accepts it as a path parameter.
    """
    try:
        if not user_id.strip():
            raise HTTPException(status_code=400, detail="user_id cannot be blank")
        rows = await fetch_search_results(user_id, org_id, limit)
    except Exception as e:
        logger.error("Failed to fetch searches: %s", e)
        raise HTTPException(status_code=500, detail="Database query failed")

    searches = [SearchResult(**row) for row in rows]
    return SearchListResponse(searches=searches, total=len(searches))


# --- Candidate: add your classification endpoints here ---
# You'll need:
# - POST /classify  (accept text, run classification, store result, return it)
# - GET /classifications/{user_id}  (retrieve stored classifications)
