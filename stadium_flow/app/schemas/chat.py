"""
Chat-related request and response schemas for the AI Concierge.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ChatRequest(BaseModel):
    """User message to the AI Concierge."""
    message: str = Field(
        min_length=1,
        max_length=1000,
        description="User's question or request",
    )
    user_zone: Optional[str] = Field(
        default=None, description="User's current zone ID for context"
    )
    session_id: Optional[str] = Field(
        default=None, description="Session ID for conversation continuity"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "message": "Where is the nearest restroom?",
            "user_zone": "block-a",
            "session_id": "sess_abc123",
        }
    }}


class ChatResponse(BaseModel):
    """AI Concierge response to the user."""
    response: str
    suggested_actions: list[str] = []
    recommended_zone: Optional[str] = None
    estimated_wait_minutes: Optional[float] = None
    session_id: str
    timestamp: str


class QuickAction(BaseModel):
    """Predefined quick action for the chat widget."""
    id: str
    label: str
    icon: str
    prompt: str
