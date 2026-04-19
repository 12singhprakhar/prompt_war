"""
WebSocket endpoint for real-time dashboard updates.

Broadcasts simulation state to connected clients at the
configured tick interval with heartbeat keep-alive.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)

# Connected WebSocket clients
connected_clients: set[WebSocket] = set()


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time dashboard updates.

    Connected clients receive:
    - Zone state updates every simulation tick
    - Alert notifications
    - Staff deployment changes
    """
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(
        "WebSocket client connected (total: %d)", len(connected_clients)
    )

    try:
        # Send initial state
        from app.main import simulation_engine
        initial_state = simulation_engine.get_state()
        await websocket.send_json({
            "type": "initial_state",
            "data": initial_state,
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (ping/pong, commands)
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
                message = json.loads(data)

                # Handle client commands
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message.get("type") == "request_state":
                    state = simulation_engine.get_state()
                    await websocket.send_json({
                        "type": "state_update",
                        "data": state,
                    })

            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        connected_clients.discard(websocket)
        logger.info(
            "WebSocket client removed (remaining: %d)", len(connected_clients)
        )


async def broadcast_state(state: dict[str, Any]) -> None:
    """
    Broadcast simulation state to all connected WebSocket clients.

    Called by the simulation engine on each tick.
    Automatically removes disconnected clients.
    """
    if not connected_clients:
        return

    message = json.dumps({"type": "state_update", "data": state})
    disconnected = set()

    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)

    # Clean up disconnected clients
    for client in disconnected:
        connected_clients.discard(client)
