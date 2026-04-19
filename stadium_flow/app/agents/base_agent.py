"""
Base Agent — Abstract foundation for the multi-agent system.

Defines the Perceive → Decide → Act lifecycle and provides
a shared memory bus for inter-agent communication.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional


logger = logging.getLogger(__name__)


class SharedMemory:
    """
    Shared memory bus for inter-agent communication.

    Implements a publish-subscribe pattern where agents can
    write state updates and subscribe to events from other agents.
    This follows the Cloud Pub/Sub architectural pattern.
    """

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}
        self._subscribers: dict[str, list] = {}
        self._event_log: list[dict] = []
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, data: Any, source: str = "") -> None:
        """
        Publish data to a topic on the shared bus.

        Args:
            topic: Event topic name (e.g., "crowd.alert", "zone.update").
            data: Payload data to publish.
            source: Agent identifier that published the event.
        """
        async with self._lock:
            self._state[topic] = data
            event = {
                "topic": topic,
                "data": data,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._event_log.append(event)

            # Keep log bounded
            if len(self._event_log) > 500:
                self._event_log = self._event_log[-250:]

        # Notify subscribers
        for callback in self._subscribers.get(topic, []):
            try:
                await callback(data)
            except Exception as e:
                logger.error("Subscriber error on topic '%s': %s", topic, e)

    async def subscribe(self, topic: str, callback) -> None:
        """
        Subscribe to a topic with a callback function.

        Args:
            topic: Event topic to subscribe to.
            callback: Async function called when topic receives data.
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    async def get(self, topic: str) -> Optional[Any]:
        """Get the latest value for a topic."""
        return self._state.get(topic)

    async def get_recent_events(self, limit: int = 20) -> list[dict]:
        """Get the most recent events from the bus."""
        return self._event_log[-limit:]


class BaseAgent(ABC):
    """
    Abstract base class for venue management agents.

    Each agent follows the Perceive → Decide → Act lifecycle:
    1. Perceive: Gather information from sensors and shared memory
    2. Decide: Analyze data and determine actions
    3. Act: Execute actions and publish results

    Attributes:
        name: Human-readable agent name.
        agent_id: Unique identifier for the agent.
        memory: Reference to the shared memory bus.
    """

    def __init__(self, name: str, agent_id: str, memory: SharedMemory) -> None:
        self.name = name
        self.agent_id = agent_id
        self.memory = memory
        self.is_active = False
        self.cycle_count = 0
        self.logger = logging.getLogger(f"agent.{agent_id}")

    @abstractmethod
    async def perceive(self) -> dict[str, Any]:
        """
        Gather information from the environment.

        Returns:
            Dictionary of perceived environmental data.
        """
        ...

    @abstractmethod
    async def decide(self, perception: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Analyze perceived data and determine actions.

        Args:
            perception: Data gathered during the perceive phase.

        Returns:
            List of action dictionaries to execute.
        """
        ...

    @abstractmethod
    async def act(self, actions: list[dict[str, Any]]) -> None:
        """
        Execute determined actions and publish results.

        Args:
            actions: List of action dictionaries from decide phase.
        """
        ...

    async def run_cycle(self) -> None:
        """Execute one complete Perceive → Decide → Act cycle."""
        try:
            self.cycle_count += 1
            perception = await self.perceive()
            actions = await self.decide(perception)
            await self.act(actions)
        except Exception as e:
            self.logger.error("Agent cycle error: %s", e, exc_info=True)

    async def start(self, interval: float = 3.0) -> None:
        """
        Start the agent's continuous operation loop.

        Args:
            interval: Seconds between cycles.
        """
        self.is_active = True
        self.logger.info("Agent '%s' started (interval=%.1fs)", self.name, interval)

        while self.is_active:
            await self.run_cycle()
            await asyncio.sleep(interval)

    async def stop(self) -> None:
        """Stop the agent."""
        self.is_active = False
        self.logger.info("Agent '%s' stopped after %d cycles", self.name, self.cycle_count)
