"""
API Middleware — CORS, request tracing, and error handling.

Provides cross-cutting concerns for all API endpoints.
"""

import time
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import correlation_id_var, generate_correlation_id

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """
    Configure all middleware for the FastAPI application.

    Adds:
    - CORS middleware for cross-origin requests
    - Request tracing with correlation IDs
    - Response timing headers
    """
    settings = get_settings()

    # CORS — Cross-Origin Resource Sharing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_tracing(request: Request, call_next) -> Response:
        """Add correlation ID and timing to all requests."""
        # Generate correlation ID
        cid = generate_correlation_id()
        correlation_id_var.set(cid)

        # Track request timing
        start_time = time.time()

        response: Response = await call_next(request)

        # Add timing and tracing headers
        duration = time.time() - start_time
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        # Log request
        logger.info(
            "%s %s → %d (%.3fs)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )

        return response
