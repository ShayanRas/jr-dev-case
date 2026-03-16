"""Request and response schemas for the API layer.

These Pydantic models define the contract between the frontend and the API.
The API layer validates incoming requests and formats outgoing responses.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Chat ---


class ChatRequest(BaseModel):
    """Request to send a message to the agent."""

    message: str = Field(..., min_length=1, description="The user's message")
    user_id: str = Field(
        ..., min_length=1, description="Authenticated user ID"
    )
    org_id: str = Field(default="", description="Organization ID")


class ChatResponse(BaseModel):
    """Response from the agent."""

    response: str = Field(..., description="The agent's response text")
    search_results_stored: int = Field(
        default=0, description="Number of new search results persisted"
    )


# --- Search History ---


class SearchResult(BaseModel):
    """A single stored search result."""

    id: int
    user_id: str
    org_id: Optional[str] = None
    query: str
    results: Any  # JSONB -- list of dicts
    created_at: datetime


class SearchListResponse(BaseModel):
    """List of stored search results."""

    searches: list[SearchResult]
    total: int


# --- Candidate: add your classification schemas here ---
# You'll need at minimum:
# - ClassifyRequest (input text + user context)
# - ClassificationResponse (the classification result)
# - ClassificationListResponse (list of past classifications)
