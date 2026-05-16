from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Dict
from app.models import HealthEvent, HealthStatus
import asyncio
import logging
from app.health import re_evaluate_dependents
import networkx as nx

logger = logging.getLogger(__name__)
EventHandler = Callable[[HealthEvent], Awaitable[None]]


class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: HealthEvent) -> None:
        pass

    @abstractmethod
    async def consume(self, handler: EventHandler) -> None:
        pass


class LocalEventBus(EventBus):
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()

    async def publish(self, event: HealthEvent) -> None:
        await self._queue.put(event)
        logger.info(
            f"Published event: Event published to local event bus",
            extra={"component_id": event.component_id, "status": event.status},
        )

    async def consume(self, handler: EventHandler) -> None:
        logger.info("Starting to consume events from local event bus")
        while True:
            event: HealthEvent = await self._queue.get()
            await handler(event)
            self._queue.task_done()


def create_event_bus() -> EventBus:
    # For now, we are using a local in-memory event bus. In the future, this can be extended to support distributed event buses like RabbitMQ or Kafka.
    return LocalEventBus()


async def process_event(
    event: HealthEvent, dag: nx.DiGraph, health_state: Dict[str, HealthStatus]
) -> None:
    if dag is None or event.component_id not in dag:
        logger.warning(
            f"Received event for unknown component: Event ignored",
            extra={"component_id": event.component_id, "status": event.status},
        )
        return
    previous_status = health_state.get(event.component_id, HealthStatus.UNKNOWN)
    health_state[event.component_id] = event.status
    logger.info(
        f"Processed health event: Health status updated",
        extra={
            "component_id": event.component_id,
            "previous_status": previous_status,
            "new_status": event.status,
            "reason": event.details,
        },
    )
    await re_evaluate_dependents(dag, health_state, event.component_id)
