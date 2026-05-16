import pytest
from app.dag import create_dag
from app.events import process_event
from app.models import ComponentInput, HealthEvent, HealthStatus


@pytest.mark.asyncio
async def test_process_event_degrades_direct_dependents():
    components = [
        ComponentInput(id="dbservice", name="Database Service", dependencies=[]),
        ComponentInput(id="apiservice", name="API Service", dependencies=["dbservice"]),
        ComponentInput(id="frontend", name="Frontend Service", dependencies=["apiservice"]),
    ]

    dag = create_dag(components)
    health_state = {
        "dbservice": HealthStatus.HEALTHY,
        "apiservice": HealthStatus.HEALTHY,
        "frontend": HealthStatus.HEALTHY,
    }

    event = HealthEvent(component_id="dbservice", status=HealthStatus.UNHEALTHY, details="Database connection timeout")
    await process_event(event, dag, health_state)

    assert health_state["dbservice"] == HealthStatus.UNHEALTHY
    assert health_state["apiservice"] == HealthStatus.DEGRADED
    assert health_state["frontend"] == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_process_event_propagates_to_indirect_dependents():
    components = [
        ComponentInput(id="dbservice", name="Database Service", dependencies=[]),
        ComponentInput(id="apiservice", name="API Service", dependencies=["dbservice"]),
        ComponentInput(id="frontend", name="Frontend Service", dependencies=["apiservice"]),
    ]

    dag = create_dag(components)
    health_state = {
        "dbservice": HealthStatus.HEALTHY,
        "apiservice": HealthStatus.HEALTHY,
        "frontend": HealthStatus.HEALTHY,
    }

    event = HealthEvent(component_id="apiservice", status=HealthStatus.UNHEALTHY, details="API outage")
    await process_event(event, dag, health_state)

    assert health_state["apiservice"] == HealthStatus.UNHEALTHY
    assert health_state["frontend"] == HealthStatus.DEGRADED
    assert health_state["dbservice"] == HealthStatus.HEALTHY
