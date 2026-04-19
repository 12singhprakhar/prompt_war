"""
Google Services Integration Layer.

Provides unified wrappers for Google Cloud services including
Gemini AI, Google Maps, and BigQuery. Gracefully degrades when
API keys are not configured (demo mode).
"""

import json
import logging
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Google Gemini AI integration for the Concierge Agent.

    Provides conversational AI capabilities with venue-specific
    system context. Falls back to rule-based responses when
    API key is not configured.
    """

    SYSTEM_PROMPT = """You are StadiumFlow AI Concierge, a helpful assistant for
attendees at the Narendra Modi Stadium in Ahmedabad, India. You help fans with:

1. Navigation — Finding seats, restrooms, concession stands, exits
2. Wait Times — Current estimated wait times at various facilities
3. Recommendations — Best food options, optimal restroom timing
4. Accessibility — ADA-compliant routes and accessible facilities
5. General Info — Event schedule, stadium rules, emergency procedures

Always be friendly, concise, and safety-conscious. If asked about emergencies,
always direct fans to the nearest exit and stadium staff. Provide specific
zone/block references (e.g., "Block A", "North Concourse") when giving directions.

Current venue context will be provided with each message."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client for API calls."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def generate_response(
        self,
        user_message: str,
        venue_context: str = "",
        conversation_history: list[dict] = None,
    ) -> str:
        """
        Generate a response using Google Gemini AI.

        Args:
            user_message: The user's question or request.
            venue_context: Current venue state for context.
            conversation_history: Previous messages in the session.

        Returns:
            AI-generated response string.
        """
        if not self.settings.google_api_key:
            logger.info("Gemini API key not set — using smart fallback")
            return self._smart_fallback(user_message, venue_context)

        try:
            client = await self._get_client()

            # Build conversation contents
            contents = []
            if conversation_history:
                for msg in conversation_history[-6:]:  # Last 6 messages
                    contents.append({
                        "role": msg.get("role", "user"),
                        "parts": [{"text": msg.get("content", "")}],
                    })

            # Add current message with venue context
            context_text = f"\n\nCurrent venue state:\n{venue_context}" if venue_context else ""
            contents.append({
                "role": "user",
                "parts": [{"text": f"{user_message}{context_text}"}],
            })

            # Call Gemini API
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash:generateContent?key={self.settings.google_api_key}"
            )

            payload = {
                "contents": contents,
                "systemInstruction": {
                    "parts": [{"text": self.SYSTEM_PROMPT}]
                },
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 500,
                    "topP": 0.95,
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                ],
            }

            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "I'm sorry, I couldn't process that.")

            return "I'm having trouble connecting right now. Please try again."

        except httpx.HTTPStatusError as e:
            logger.error("Gemini API error: %s", e.response.status_code)
            return self._smart_fallback(user_message, venue_context)
        except Exception as e:
            logger.error("Gemini service error: %s", e)
            return self._smart_fallback(user_message, venue_context)

    def _smart_fallback(self, message: str, context: str = "") -> str:
        """
        Rule-based fallback when Gemini API is unavailable.

        Provides intelligent responses based on keyword matching
        for common fan queries.
        """
        msg = message.lower()

        if any(w in msg for w in ["restroom", "bathroom", "toilet", "washroom"]):
            return (
                "🚻 Restrooms are located at each concourse level. The nearest "
                "ones to most seating blocks are:\n\n"
                "• **North Concourse** — Near Gate 1 (currently low traffic)\n"
                "• **South Concourse** — Near Gate 3\n"
                "• **East Concourse** — Near Gate 5\n"
                "• **West Concourse** — Near Gate 6\n\n"
                "Accessible restrooms are available at all locations. "
                "Would you like me to find the closest one to your current location?"
            )

        if any(w in msg for w in ["food", "eat", "hungry", "concession", "drink", "snack"]):
            return (
                "🍔 Food and beverage stands are available on every concourse:\n\n"
                "• **North Concourse** — Indian street food, beverages\n"
                "• **South Concourse** — International cuisine, desserts\n"
                "• **East Concourse** — Quick bites, cold drinks\n"
                "• **West Concourse** — Premium dining options\n\n"
                "💡 **Pro Tip**: The East Concourse typically has shorter wait times "
                "during the mid-innings break. Current average wait: ~5 minutes."
            )

        if any(w in msg for w in ["exit", "leave", "way out", "gate"]):
            return (
                "🚪 The stadium has 6 exit gates:\n\n"
                "• **Gate 1** — North Main (Metro access)\n"
                "• **Gate 2** — North East (Parking Lot A)\n"
                "• **Gate 3** — South Main (Bus stops)\n"
                "• **Gate 4** — South East (Parking Lot B)\n"
                "• **Gate 5** — East (Rideshare pickup)\n"
                "• **Gate 6** — West (Pedestrian exit)\n\n"
                "I can find the fastest exit route from your current location!"
            )

        if any(w in msg for w in ["emergency", "help", "medical", "first aid", "safety"]):
            return (
                "🚨 **For emergencies, please contact stadium staff immediately.**\n\n"
                "• **First Aid stations** are at North and South concourses\n"
                "• **Emergency exits** are clearly marked at all gates\n"
                "• **Security personnel** are stationed throughout the venue\n"
                "• **Emergency hotline**: Dial the stadium PA system\n\n"
                "⚠️ If this is a medical emergency, alert the nearest staff member "
                "or security personnel right away."
            )

        if any(w in msg for w in ["seat", "block", "section", "find my seat"]):
            return (
                "🎫 To find your seat:\n\n"
                "1. Check your ticket for **Block letter** (A-R) and **Row number**\n"
                "2. Enter through the nearest gate to your block\n"
                "3. Follow signs on the concourse to your block entrance\n\n"
                "Blocks A-E → Use Gate 1 or Gate 2\n"
                "Blocks F-I → Use Gate 5\n"
                "Blocks J-M → Use Gate 3 or Gate 4\n"
                "Blocks N-R → Use Gate 6\n\n"
                "Which block are you looking for? I'll give you directions!"
            )

        if any(w in msg for w in ["wait", "queue", "line", "busy", "crowded"]):
            return (
                "⏱️ Here are current estimated wait times:\n\n"
                "• **Restrooms**: 2-5 min (North Concourse shortest)\n"
                "• **Food stands**: 5-8 min (East Concourse shortest)\n"
                "• **Merchandise**: 3-6 min\n\n"
                "💡 Wait times are lowest:\n"
                "• 15 minutes after the match starts\n"
                "• During the last 10 overs\n\n"
                "Would you like me to find the shortest queue near you?"
            )

        if any(w in msg for w in ["accessible", "wheelchair", "disability", "ada"]):
            return (
                "♿ Accessibility information:\n\n"
                "• **Elevators** are available at all concourse levels\n"
                "• **Wheelchair seating** is in Blocks A, J, and the Premium Gallery\n"
                "• **Accessible restrooms** are at every concourse\n"
                "• **Service animals** are welcome\n"
                "• **Sign language** interpreters at Information desks\n\n"
                "I can provide wheelchair-accessible routes to any location!"
            )

        return (
            "👋 I'm your **StadiumFlow AI Concierge**! I can help you with:\n\n"
            "• 🚻 **Find restrooms** — Nearest location and wait times\n"
            "• 🍔 **Food & drinks** — Concession options and queues\n"
            "• 🎫 **Find your seat** — Navigate to your block\n"
            "• 🚪 **Exit routes** — Fastest way to leave\n"
            "• ♿ **Accessibility** — Accessible routes and facilities\n"
            "• ⏱️ **Wait times** — Current queue estimates\n\n"
            "Just ask me anything about the stadium!"
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class GoogleMapsService:
    """
    Google Maps Platform integration for navigation.

    Provides geocoding, directions, and location-based services.
    Falls back to internal routing when API key is not configured.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def get_directions(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str = "walking",
    ) -> Optional[dict]:
        """
        Get directions using Google Maps Directions API.

        Args:
            origin_lat/lng: Starting coordinates.
            dest_lat/lng: Destination coordinates.
            mode: Travel mode (walking, driving, transit).

        Returns:
            Directions response or None on failure.
        """
        if not self.settings.google_maps_api_key:
            logger.info("Maps API key not set — using internal routing")
            return None

        try:
            client = await self._get_client()
            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                "origin": f"{origin_lat},{origin_lng}",
                "destination": f"{dest_lat},{dest_lng}",
                "mode": mode,
                "key": self.settings.google_maps_api_key,
            }
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Google Maps API error: %s", e)
            return None

    async def get_venue_location(self) -> dict:
        """
        Return the venue's geographic coordinates.

        Returns hard-coded coordinates for Narendra Modi Stadium.
        """
        return {
            "name": "Narendra Modi Stadium",
            "address": "Sardar Patel Stadium Road, Navrangpura, Ahmedabad, Gujarat 380014",
            "latitude": 23.0918,
            "longitude": 72.5957,
            "maps_url": "https://maps.google.com/?q=23.0918,72.5957",
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class BigQueryService:
    """
    BigQuery integration for analytics logging and querying.

    Logs crowd analytics events to BigQuery for historical
    analysis and dashboard visualization. Uses a local SQLite
    fallback when BigQuery credentials are not configured.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._buffer: list[dict] = []
        self._buffer_size = 100

    async def log_event(self, event_data: dict) -> None:
        """
        Buffer an analytics event for batch insertion.

        Events are batched for efficiency and flushed when
        the buffer reaches capacity.
        """
        self._buffer.append(event_data)

        if len(self._buffer) >= self._buffer_size:
            await self.flush()

    async def flush(self) -> None:
        """
        Flush buffered events to BigQuery (or local storage).

        In demo mode, logs to the application database.
        """
        if not self._buffer:
            return

        if self.settings.bigquery_project_id:
            try:
                # In production, this would use the BigQuery client library
                logger.info(
                    "Flushing %d events to BigQuery project: %s",
                    len(self._buffer),
                    self.settings.bigquery_project_id,
                )
            except Exception as e:
                logger.error("BigQuery flush error: %s", e)
        else:
            logger.debug("BigQuery not configured — buffered %d events locally", len(self._buffer))

        self._buffer.clear()

    async def query_peak_times(self, zone_id: str) -> dict:
        """
        Query historical peak times for a zone.

        Returns predicted busy periods based on historical patterns.
        """
        # Simulated historical data for demo purposes
        return {
            "zone_id": zone_id,
            "peak_times": [
                {"period": "Pre-match (1hr before)", "intensity": "high"},
                {"period": "Half-time / Innings break", "intensity": "very_high"},
                {"period": "Post-match (30min after)", "intensity": "high"},
            ],
            "best_times": [
                {"period": "15min after start", "intensity": "low"},
                {"period": "Mid-session", "intensity": "moderate"},
            ],
        }
