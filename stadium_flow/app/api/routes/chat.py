"""
Chat API endpoints — AI Concierge.

Provides the conversational interface for fan assistance
using Google Gemini AI with venue context.
"""

from fastapi import APIRouter, Depends

from app.core.security import check_rate_limit
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["AI Concierge"])


@router.post(
    "/message",
    response_model=ChatResponse,
    summary="Send message to AI Concierge",
    description="Chat with the AI Concierge for venue assistance, directions, and recommendations.",
    dependencies=[Depends(check_rate_limit)],
)
async def send_message(request: ChatRequest) -> ChatResponse:
    """Process a chat message and return AI-generated response."""
    from app.main import concierge_agent

    result = await concierge_agent.handle_chat(
        message=request.message,
        user_zone=request.user_zone,
        session_id=request.session_id,
    )

    return ChatResponse(**result)


@router.get(
    "/quick-actions",
    summary="Get quick actions",
    description="Get predefined quick action buttons for the chat widget.",
)
async def get_quick_actions() -> dict:
    """Get available quick action prompts."""
    from app.main import concierge_agent
    actions = await concierge_agent.get_quick_actions()
    return {"actions": actions}
