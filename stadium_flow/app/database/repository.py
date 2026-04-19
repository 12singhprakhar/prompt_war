"""
Repository pattern for database operations.

Provides a clean data access layer that abstracts SQL queries
behind domain-specific methods.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from app.database.connection import get_db
from app.models.event import Event

logger = logging.getLogger(__name__)


class EventRepository:
    """Data access layer for event/alert persistence."""

    async def save_event(self, event: Event) -> None:
        """
        Persist an event to the database.

        Args:
            event: Event model instance to save.
        """
        db = await get_db()
        await db.execute(
            """INSERT OR REPLACE INTO events
               (id, event_type, severity, source_agent, title, message,
                zone_id, metadata, timestamp, is_resolved)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id,
                event.event_type.value,
                event.severity.value,
                event.source_agent,
                event.title,
                event.message,
                event.zone_id,
                json.dumps(event.metadata),
                event.timestamp.isoformat(),
                int(event.is_resolved),
            ),
        )
        await db.commit()

    async def get_recent_events(self, limit: int = 50) -> list[dict]:
        """
        Retrieve the most recent events.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of event dictionaries ordered by timestamp descending.
        """
        db = await get_db()
        async with db.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_active_alerts(self) -> list[dict]:
        """Get all unresolved events."""
        db = await get_db()
        async with db.execute(
            """SELECT * FROM events
               WHERE is_resolved = 0
               ORDER BY timestamp DESC""",
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def resolve_event(self, event_id: str) -> None:
        """Mark an event as resolved."""
        db = await get_db()
        await db.execute(
            "UPDATE events SET is_resolved = 1 WHERE id = ?",
            (event_id,),
        )
        await db.commit()


class AnalyticsRepository:
    """Data access layer for time-series crowd analytics."""

    async def log_zone_snapshot(
        self,
        zone_id: str,
        occupancy: int,
        capacity: int,
        status: str,
    ) -> None:
        """
        Record a point-in-time zone occupancy snapshot.

        Used for historical trend analysis and BigQuery sync.
        """
        db = await get_db()
        ratio = occupancy / capacity if capacity > 0 else 0.0
        await db.execute(
            """INSERT INTO analytics
               (zone_id, occupancy, capacity, occupancy_ratio, status, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                zone_id,
                occupancy,
                capacity,
                round(ratio, 4),
                status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()

    async def get_zone_history(
        self, zone_id: str, limit: int = 100
    ) -> list[dict]:
        """Get historical snapshots for a specific zone."""
        db = await get_db()
        async with db.execute(
            """SELECT * FROM analytics
               WHERE zone_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (zone_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class ChatRepository:
    """Data access layer for chat session persistence."""

    async def save_message(
        self, session_id: str, role: str, content: str
    ) -> None:
        """Save a chat message to the session history."""
        db = await get_db()
        await db.execute(
            """INSERT INTO chat_sessions (session_id, role, content, timestamp)
               VALUES (?, ?, ?, ?)""",
            (session_id, role, content, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()

    async def get_session_history(
        self, session_id: str, limit: int = 20
    ) -> list[dict]:
        """Retrieve conversation history for a session."""
        db = await get_db()
        async with db.execute(
            """SELECT role, content, timestamp FROM chat_sessions
               WHERE session_id = ?
               ORDER BY timestamp ASC LIMIT ?""",
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
