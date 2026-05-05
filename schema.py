"""
Lab 8: API request/response contracts (Pydantic).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Inbound chat payload: user message maps to the graph ``topic`` field."""

    message: str = Field(..., min_length=1, description="Blog topic or user instruction")
    thread_id: str = Field(
        ...,
        min_length=1,
        description="Stable id for LangGraph checkpointing (UUID string recommended)",
    )


class ChatResponse(BaseModel):
    """Outbound result after one graph invocation."""

    final_answer: str = Field(
        ...,
        description="Merged markdown at interrupt, final text when completed, or refusal if blocked",
    )
    status: str = Field(
        ...,
        description="completed | interrupted_awaiting_hitl | blocked | error",
    )
