from fastapi import BackgroundTasks, FastAPI, status, HTTPException
from app.models import (
    SystemRegisteredResponse,
    SystemInput,
    ComponentInput,
    HealthStatus,
    SystemHealthStatusResponse,
    HealthEvent,
)
from typing import Dict, Optional
import os
import sys
import networkx as nx
from app.events import create_event_bus, process_event, LocalEventBus
import asyncio
from app.dag import (
    create_dag,
    ComponentNotFoundError,
    CycleDetectedError,
    get_dag_summary,
)
import structlog
import logging
from app.health import evaluate_health
from app.summary import generate_system_health_summary
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

dag: Optional[nx.DiGraph] = None
componenent_registry: Dict[str, ComponentInput] = {}
health_status: Dict[str, HealthStatus] = (
    {}
)  # This will hold the health status of each component
event_bus = create_event_bus()
_consumer_task: Optional[asyncio.Task] = None

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
)

logging.basicConfig(level=logging.INFO)
log = structlog.get_logger()


# OpenTelemetry
_DISABLE_OTEL = os.getenv("DISABLE_OPENTELEMETRY", "0") == "1" or any("pytest" in arg for arg in sys.argv)
try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    if _DISABLE_OTEL:
        _OTELEMETRY_ENABLED = False
        log.info("OpenTelemetry tracing disabled for current environment")
    else:
        _provider = TracerProvider()
        _provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(_provider)
        _OTELEMETRY_ENABLED = True
        log.info("OpenTelemetry tracing enabled")
except ImportError:
    _OTELEMETRY_ENABLED = False
    log.warning("OpenTelemetry not available, tracing disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_task
    log.info("Starting event bus consumer task")
    _consumer_task = asyncio.create_task(_run_consumer(), name="event_bus_consumer")

    yield

    log.info("Shutting down event bus consumer task")
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            log.info("Event bus consumer task cancelled successfully")


async def _event_handler(event: HealthEvent) -> None:
    await process_event(event, dag, health_status)


async def _run_consumer() -> None:
    while True:
        try:
            await event_bus.consume(_event_handler)
        except Exception as e:
            log.error("Error in event consumer", error=str(e))
            await asyncio.sleep(2)  # Backoff before retrying


app = FastAPI(
    title="System Health Monitor",
    description="Evaluate and monitor the health of a distributed system modelled as a DAG. Supports request driven and event driven updates.",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

if _OTELEMETRY_ENABLED:
    FastAPIInstrumentor.instrument_app(app)


@app.post(
    "/register_component",
    response_model=SystemRegisteredResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new component with its dependencies to trigger health evaluation",
    tags=["Component Registration"],
)
async def register_component(
    payload: SystemInput, background_tasks: BackgroundTasks
) -> SystemRegisteredResponse:
    """
    Register a new component along with its dependencies. This will trigger the health evaluation process for the entire system.

    Example Payload:
    {
        "components": [
            { "id": "dbservice", "name": "Database Service","dependencies": [] },
            { "id": "authservice", "name": "Authentication Service","dependencies": [] },
            { "id": "apiservice", "name": "API Service","dependencies": ["authservice", "dbservice"] },
            { "id": "frontend", "name": "Frontend Service","dependencies": ["apiservice"] }
        ]
    }

    Returns a response indicating the registration status and the number of components registered.
    """

    global dag, componenent_registry, health_status

    try:
        new_dag = create_dag(payload.components)
    except ComponentNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except CycleDetectedError as e:
        raise HTTPException(status_code=422, detail=str(e))

    dag = new_dag
    componenent_registry = {component.id: component for component in payload.components}
    health_status = {
        component.id: HealthStatus.HEALTHY for component in payload.components
    }

    summary = get_dag_summary(dag)

    log.info("Registered new components and created DAG", **summary)

    background_tasks.add_task(_run_evaluation)

    return SystemRegisteredResponse(
        message="Component(s) registered successfully. Health evaluation triggered.",
        component_count=summary["component_count"],
        evaluation_levels=summary["evaluation_levels"],
    )


async def _run_evaluation() -> None:
    try:
        log.info("Starting health evaluation process")
        await evaluate_health(dag, health_status)
    except Exception as e:
        log.error("Error during health evaluation", error=str(e))


@app.get(
    "/components-status",
    response_model=SystemHealthStatusResponse,
    summary="Get the current components status for all registered components",
    tags=["Components Status"],
)
async def get_components_status() -> SystemHealthStatusResponse:
    """
    Retrieve the current components status for all registered components in the system. The response includes the overall system health status, individual component statuses, and counts of healthy, degraded, and unhealthy components.
    """
    if not dag:
        raise HTTPException(
            status_code=503,
            detail="No components registered yet. POST /register_component to register components and trigger health evaluation.",
        )

    return generate_system_health_summary(health_status, componenent_registry, dag)


@app.post(
    "/update-metrics",
    status_code=status.HTTP_201_CREATED,
    summary="Inject synthetic health events to simulate changes in component health status",
    tags=["Metrics Update"],
)
async def update_metrics(event: HealthEvent) -> dict:
    """
    Inject synthetic health events to simulate changes in component health status. This endpoint is useful for testing and simulating real-world scenarios where component health may change over time.

    Example Payload:
    {
        "component_id": "dbservice",
        "status": "unhealthy",
        "details": "Database connection timeout"
    }

    The endpoint will process the event and update the health status of the specified component accordingly.
    """
    if not dag:
        raise HTTPException(
            status_code=503,
            detail="No components registered yet. POST /register_component to register components and trigger health evaluation.",
        )

    if event.component_id not in dag:
        raise HTTPException(
            status_code=404,
            detail=f"Component with id '{event.component_id}' not found in the registered system.",
        )

    await process_event(event, dag, health_status)
    return {
        "accepted": True,
        "component_id": event.component_id,
        "new_status": event.status,
    }


@app.get(
    "/health", 
    summary="Health check endpoint for monitoring the health of this service", 
    tags=["Monitoring"])
async def health_check() -> dict:
    """Health check endpoint to verify that the System Health Monitor service is running and responsive. This can be used by monitoring tools to check the health of this service itself."""
    return {"status": "ok"}

