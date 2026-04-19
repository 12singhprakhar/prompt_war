"""
StadiumFlow AI — Main Application Entry Point.

FastAPI application with lifespan management for the simulation
engine, multi-agent system, and real-time WebSocket broadcasting.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.api.middleware import setup_middleware
from app.api.routes import venues, zones, routing, chat, websocket
from app.api.routes.websocket import broadcast_state
from app.services.simulation_engine import SimulationEngine
from app.services.routing_engine import RoutingEngine
from app.services.crowd_analytics import CrowdAnalytics
from app.agents.base_agent import SharedMemory
from app.agents.sentinel_agent import SentinelAgent
from app.agents.concierge_agent import ConciergeAgent
from app.agents.orchestra_agent import OrchestraAgent
from app.database.connection import get_db, close_db

logger = logging.getLogger(__name__)

# ── Global Service Instances ─────────────────────────────────────
# These are initialized during app lifespan startup and accessed
# by API route handlers via import.

settings = get_settings()
simulation_engine: SimulationEngine = None  # type: ignore[assignment]
routing_engine: RoutingEngine = None  # type: ignore[assignment]
crowd_analytics: CrowdAnalytics = None  # type: ignore[assignment]
shared_memory: SharedMemory = None  # type: ignore[assignment]
sentinel_agent: SentinelAgent = None  # type: ignore[assignment]
concierge_agent: ConciergeAgent = None  # type: ignore[assignment]
orchestra_agent: OrchestraAgent = None  # type: ignore[assignment]

_start_time: float = 0.0
_background_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup:
    - Initialize logging
    - Connect to database
    - Create simulation engine and services
    - Start multi-agent system
    - Begin WebSocket broadcasting

    Shutdown:
    - Stop simulation and agents
    - Close database connections
    - Clean up resources
    """
    global simulation_engine, routing_engine, crowd_analytics
    global shared_memory, sentinel_agent, concierge_agent, orchestra_agent
    global _start_time

    # ── Startup ──────────────────────────────────────────────────
    _start_time = time.time()
    setup_logging(debug=settings.debug)
    logger.info("StadiumFlow AI v%s starting...", settings.app_version)

    # Initialize database
    await get_db()

    # Create simulation engine
    simulation_engine = SimulationEngine(
        initial_count=settings.initial_attendee_count,
        max_capacity=settings.max_venue_capacity,
        tick_interval=settings.simulation_tick_interval,
    )

    # Create services
    routing_engine = RoutingEngine(simulation_engine.zones)
    crowd_analytics = CrowdAnalytics(simulation_engine.zones)
    simulation_engine.analytics_service = crowd_analytics

    # Create shared memory bus (Cloud Pub/Sub pattern)
    shared_memory = SharedMemory()

    # Create agents
    sentinel_agent = SentinelAgent(
        memory=shared_memory,
        zones=simulation_engine.zones,
        analytics=crowd_analytics,
        congestion_threshold=settings.congestion_threshold,
    )
    concierge_agent = ConciergeAgent(
        memory=shared_memory,
        zones=simulation_engine.zones,
        routing=routing_engine,
        analytics=crowd_analytics,
    )
    orchestra_agent = OrchestraAgent(
        memory=shared_memory,
        zones=simulation_engine.zones,
    )

    # Register WebSocket broadcast callback
    simulation_engine.register_callback(broadcast_state)

    # Start background tasks
    _background_tasks.append(asyncio.create_task(simulation_engine.start()))
    _background_tasks.append(asyncio.create_task(sentinel_agent.start(interval=3.0)))
    _background_tasks.append(asyncio.create_task(
        concierge_agent.start(interval=10.0)
    ))
    _background_tasks.append(asyncio.create_task(orchestra_agent.start(interval=5.0)))

    logger.info("All systems operational - %d agents active", 3)
    logger.info("Dashboard: http://%s:%d", settings.host, settings.port)
    logger.info("API Docs: http://%s:%d/docs", settings.host, settings.port)

    yield  # Application is running

    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("Shutting down StadiumFlow AI...")

    # Stop agents and simulation
    await sentinel_agent.stop()
    await concierge_agent.stop()
    await orchestra_agent.stop()
    await simulation_engine.stop()

    # Cancel background tasks
    for task in _background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Cleanup
    await concierge_agent.close()
    await close_db()
    logger.info("Shutdown complete")


# ── FastAPI Application ──────────────────────────────────────────
app = FastAPI(
    title="StadiumFlow AI",
    description=(
        "Smart venue experience platform powered by multi-agent AI. "
        "Optimizes crowd movement, reduces waiting times, and provides "
        "real-time coordination for large-scale sporting venues."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup middleware (CORS, tracing)
setup_middleware(app)

# ── API Routes ───────────────────────────────────────────────────
app.include_router(venues.router, prefix="/api/v1")
app.include_router(zones.router, prefix="/api/v1")
app.include_router(routing.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(websocket.router)

# ── Static Files (Frontend) ─────────────────────────────────────
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the main dashboard HTML page."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "StadiumFlow AI API — Visit /docs for API documentation"}


@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict:
    """System health check endpoint."""
    from app.api.routes.websocket import connected_clients

    return {
        "status": "healthy",
        "version": settings.app_version,
        "simulation_active": simulation_engine.is_running if simulation_engine else False,
        "connected_clients": len(connected_clients),
        "uptime_seconds": round(time.time() - _start_time, 1),
        "agents": {
            "sentinel": sentinel_agent.is_active if sentinel_agent else False,
            "concierge": concierge_agent.is_active if concierge_agent else False,
            "orchestra": orchestra_agent.is_active if orchestra_agent else False,
        },
    }


# ── Run with Uvicorn ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
