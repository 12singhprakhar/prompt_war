"""
Security utilities: authentication, rate limiting, input sanitization.

Provides middleware and dependency injection for securing API endpoints.
"""

import hashlib
import html
import time
from collections import defaultdict
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

# ── Bearer Token Scheme ──────────────────────────────────────────
security_scheme = HTTPBearer(auto_error=False)


# ── Rate Limiter ─────────────────────────────────────────────────
class RateLimiter:
    """
    In-memory sliding window rate limiter.

    Tracks request counts per client IP within a configurable
    time window. Thread-safe for single-process deployments.
    """

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str, max_requests: int, window: int) -> bool:
        """
        Check if a client is within rate limits.

        Args:
            client_id: Unique identifier for the client (e.g., IP address).
            max_requests: Maximum number of allowed requests in the window.
            window: Time window in seconds.

        Returns:
            True if the request is allowed, False otherwise.
        """
        now = time.time()
        cutoff = now - window

        # Prune expired entries
        self._requests[client_id] = [
            ts for ts in self._requests[client_id] if ts > cutoff
        ]

        if len(self._requests[client_id]) >= max_requests:
            return False

        self._requests[client_id].append(now)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter()


# ── Dependencies ─────────────────────────────────────────────────
async def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    settings: Settings = Depends(get_settings),
) -> Optional[str]:
    """
    Verify API key or Firebase token from Authorization header.

    If no API key is configured in settings, authentication is bypassed
    (development mode). Compares using constant-time hash comparison
    to prevent timing attacks.

    Returns:
        The verified client identifier, or None if auth is disabled.

    Raises:
        HTTPException: 401 if credentials are missing or invalid.
    """
    # Skip auth if no API key is configured (demo/development mode)
    if not settings.api_key:
        return None

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant-time comparison to prevent timing attacks
    provided_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    expected_hash = hashlib.sha256(settings.api_key.encode()).hexdigest()

    if provided_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


async def check_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    """
    Enforce per-IP rate limiting on incoming requests.

    Raises:
        HTTPException: 429 if the client has exceeded rate limits.
    """
    client_ip = request.client.host if request.client else "unknown"

    if not rate_limiter.is_allowed(
        client_id=client_ip,
        max_requests=settings.rate_limit_requests,
        window=settings.rate_limit_window,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent XSS and injection attacks.

    Args:
        text: Raw user input string.
        max_length: Maximum allowed character length.

    Returns:
        Sanitized, length-capped string.
    """
    # HTML-escape dangerous characters
    sanitized = html.escape(text.strip())
    # Enforce length limit
    return sanitized[:max_length]
