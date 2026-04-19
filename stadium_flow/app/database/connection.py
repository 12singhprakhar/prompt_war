"""
Database connection management.

Provides async SQLite connection via aiosqlite with
connection pooling and schema initialization.
"""

import aiosqlite
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Global database connection
_db_connection: Optional[aiosqlite.Connection] = None
_db_path: str = "stadiumflow.db"


async def get_db() -> aiosqlite.Connection:
    """
    Get the database connection, creating it if necessary.

    Returns:
        Active aiosqlite connection.
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(_db_path)
        _db_connection.row_factory = aiosqlite.Row
        await _initialize_schema(_db_connection)
        logger.info("Database connection established: %s", _db_path)
    return _db_connection


async def close_db() -> None:
    """Close the database connection gracefully."""
    global _db_connection
    if _db_connection:
        await _db_connection.close()
        _db_connection = None
        logger.info("Database connection closed")


async def _initialize_schema(db: aiosqlite.Connection) -> None:
    """
    Create database tables if they don't exist.

    Tables:
        - events: Audit log for all system events/alerts.
        - analytics: Time-series data for crowd analytics.
        - chat_sessions: Conversation history for AI concierge.
    """
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            source_agent TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            zone_id TEXT,
            metadata TEXT DEFAULT '{}',
            timestamp TEXT NOT NULL,
            is_resolved INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id TEXT NOT NULL,
            occupancy INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            occupancy_ratio REAL NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_analytics_zone ON analytics(zone_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_sessions(session_id);
    """)
    await db.commit()
    logger.info("Database schema initialized")
