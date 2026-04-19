"""
Concierge Agent — Fan Assistant.

Provides personalized assistance to attendees using Google Gemini AI
for natural language understanding and context-aware responses.
Integrates with Google Maps for navigation and venue state for
real-time recommendations.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.agents.base_agent import BaseAgent, SharedMemory
from app.core.security import sanitize_input
from app.models.zone import Zone
from app.services.google_services import GeminiService, GoogleMapsService
from app.services.routing_engine import RoutingEngine
from app.services.crowd_analytics import CrowdAnalytics
from app.database.repository import ChatRepository


class ConciergeAgent(BaseAgent):
    """
    Fan-facing AI assistant powered by Google Gemini.

    Responsibilities:
    - Natural language interaction with attendees
    - Context-aware venue navigation assistance
    - Personalized recommendations based on crowd state
    - Accessible facility finding with Google Maps integration
    """

    # Quick actions available in the chat widget
    QUICK_ACTIONS = [
        {"id": "find-restroom", "label": "Find Restroom", "icon": "🚻", "prompt": "Where is the nearest restroom?"},
        {"id": "find-food", "label": "Find Food", "icon": "🍔", "prompt": "What food options are available?"},
        {"id": "find-exit", "label": "Find Exit", "icon": "🚪", "prompt": "How do I get to the nearest exit?"},
        {"id": "wait-times", "label": "Wait Times", "icon": "⏱️", "prompt": "What are the current wait times?"},
        {"id": "find-seat", "label": "Find My Seat", "icon": "🎫", "prompt": "Help me find my seat"},
        {"id": "accessibility", "label": "Accessibility", "icon": "♿", "prompt": "What accessible facilities are available?"},
    ]

    def __init__(
        self,
        memory: SharedMemory,
        zones: dict[str, Zone],
        routing: RoutingEngine,
        analytics: CrowdAnalytics,
    ) -> None:
        super().__init__(
            name="Concierge Agent",
            agent_id="concierge",
            memory=memory,
        )
        self.zones = zones
        self.routing = routing
        self.analytics = analytics
        self.gemini = GeminiService()
        self.maps = GoogleMapsService()
        self.chat_repo = ChatRepository()

        # Active session tracking
        self._sessions: dict[str, list[dict]] = {}

    async def perceive(self) -> dict[str, Any]:
        """Gather current venue state for context injection."""
        congestion = self.analytics.get_congestion_summary()
        crowd_intel = await self.memory.get("crowd.intelligence") or {}

        return {
            "congestion": congestion,
            "active_alerts": crowd_intel.get("active_alerts", []),
            "recommendations": crowd_intel.get("recommendations", []),
        }

    async def decide(self, perception: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Concierge decides reactively — actions are driven by user chat
        messages, not by periodic cycles. This method updates internal
        context for when a chat message arrives.
        """
        # Update context for next chat interaction
        self._current_context = perception
        return []  # No autonomous actions

    async def act(self, actions: list[dict[str, Any]]) -> None:
        """No autonomous actions for concierge — it's reactive."""
        pass

    async def handle_chat(
        self,
        message: str,
        user_zone: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process a user chat message and generate a response.

        This is the main entry point for fan interactions. Combines
        Gemini AI with venue context for intelligent responses.

        Args:
            message: User's message (already sanitized).
            user_zone: User's current zone for location-aware responses.
            session_id: Session ID for conversation continuity.

        Returns:
            Response dictionary with AI response and metadata.
        """
        # Generate or reuse session
        if not session_id:
            session_id = f"sess-{uuid.uuid4().hex[:8]}"

        # Sanitize input
        clean_message = sanitize_input(message, max_length=1000)

        # Build venue context string
        venue_context = self._build_venue_context(user_zone)

        # Get conversation history
        history = self._sessions.get(session_id, [])

        # Save user message
        history.append({"role": "user", "content": clean_message})
        try:
            await self.chat_repo.save_message(session_id, "user", clean_message)
        except Exception:
            pass

        # Generate AI response
        response_text = await self.gemini.generate_response(
            user_message=clean_message,
            venue_context=venue_context,
            conversation_history=history,
        )

        # Save AI response
        history.append({"role": "model", "content": response_text})
        self._sessions[session_id] = history[-20:]  # Keep last 20 messages
        try:
            await self.chat_repo.save_message(session_id, "model", response_text)
        except Exception:
            pass

        # Detect if user is asking for navigation
        suggested_actions = self._extract_suggestions(clean_message)
        recommended_zone = self._detect_destination(clean_message)

        # Estimate wait time if relevant
        wait_time = None
        if recommended_zone:
            wait_time = self.analytics.estimate_wait_time(recommended_zone)

        self.logger.info(
            "Chat [%s]: user=%s → response length=%d",
            session_id, clean_message[:50], len(response_text),
        )

        return {
            "response": response_text,
            "suggested_actions": suggested_actions,
            "recommended_zone": recommended_zone,
            "estimated_wait_minutes": wait_time,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _build_venue_context(self, user_zone: Optional[str] = None) -> str:
        """Build a concise venue state string for Gemini context."""
        lines = ["Current Venue Status:"]

        # Overall stats
        total = sum(z.current_occupancy for z in self.zones.values())
        lines.append(f"Total attendees: {total:,}")

        # Critical zones
        critical = [z for z in self.zones.values() if z.status.value == "critical"]
        if critical:
            lines.append(f"⚠️ Critical zones: {', '.join(z.name for z in critical)}")

        # User's zone context
        if user_zone and user_zone in self.zones:
            zone = self.zones[user_zone]
            lines.append(
                f"User is in {zone.name} ({zone.occupancy_ratio:.0%} full, "
                f"status: {zone.status.value})"
            )

        return "\n".join(lines)

    def _extract_suggestions(self, message: str) -> list[str]:
        """Extract suggested follow-up actions from the user's message."""
        msg = message.lower()
        suggestions = []

        if any(w in msg for w in ["restroom", "bathroom"]):
            suggestions.extend(["Show route to nearest restroom", "Check wait times"])
        elif any(w in msg for w in ["food", "eat", "drink"]):
            suggestions.extend(["Show food options nearby", "Compare wait times"])
        elif any(w in msg for w in ["exit", "leave"]):
            suggestions.extend(["Show fastest exit", "Check gate congestion"])
        elif any(w in msg for w in ["seat", "block"]):
            suggestions.extend(["Show route to my seat", "View venue map"])

        if not suggestions:
            suggestions = ["View venue map", "Check wait times", "Find nearest exit"]

        return suggestions

    def _detect_destination(self, message: str) -> Optional[str]:
        """Detect if the user's message implies a destination zone."""
        msg = message.lower()

        # Map common queries to zone types
        if any(w in msg for w in ["restroom", "bathroom", "toilet"]):
            return "concourse-north"  # Restrooms are on concourses
        if any(w in msg for w in ["exit", "gate", "leave"]):
            return "gate-1"
        if any(w in msg for w in ["food", "concession"]):
            return "concourse-east"

        # Check for specific block mentions
        for letter in "abcdefghijklmnopqr":
            if f"block {letter}" in msg or f"block-{letter}" in msg:
                return f"block-{letter}"

        return None

    async def get_quick_actions(self) -> list[dict]:
        """Return available quick actions for the chat widget."""
        return self.QUICK_ACTIONS

    async def close(self) -> None:
        """Cleanup resources."""
        await self.gemini.close()
        await self.maps.close()
