from datetime import datetime, timezone
from typing import List, Dict
import networkx as nx
from app.models import (
    ComponentHealth,
    HealthStatus,
    SystemHealthStatusResponse,
    ComponentInput,
)
from app.dag import get_dependencies


def overall_health(health_state: Dict[str, HealthStatus]) -> HealthStatus:
    statuses = set(health_state.values())
    if HealthStatus.UNHEALTHY in statuses:
        return HealthStatus.UNHEALTHY
    elif HealthStatus.DEGRADED in statuses:
        return HealthStatus.DEGRADED
    elif HealthStatus.UNKNOWN in statuses:
        return HealthStatus.UNKNOWN
    else:
        return HealthStatus.HEALTHY


def generate_system_health_summary(
    health_state: Dict[str, HealthStatus],
    component_registry: Dict[str, ComponentInput],
    dag: nx.DiGraph,
) -> SystemHealthStatusResponse:

    component_health_priority = {
        HealthStatus.UNHEALTHY: 0,
        HealthStatus.DEGRADED: 1,
        HealthStatus.UNKNOWN: 2,
        HealthStatus.HEALTHY: 3,
    }

    components: List[ComponentHealth] = []
    counts = {s: 0 for s in HealthStatus}

    for component_id, component in component_registry.items():
        status = health_state.get(component_id, HealthStatus.UNKNOWN)
        counts[status] += 1

        dependencies = get_dependencies(dag, component_id)
        alert = status in {HealthStatus.UNHEALTHY, HealthStatus.DEGRADED}

        components.append(
            ComponentHealth(
                id=component_id,
                name=component.name,
                status=status,
                dependencies=dependencies,
                alert=alert,
            )
        )

    # Sort components by severity (unhealthy first)
    components.sort(key=lambda c: component_health_priority[c.status])

    return SystemHealthStatusResponse(
        overall_status=overall_health(health_state),
        componenets=components,
        evaluatedatetime=datetime.now().astimezone(),
        unhealthy_count=counts[HealthStatus.UNHEALTHY],
        degraded_count=counts[HealthStatus.DEGRADED],
        healthy_count=counts[HealthStatus.HEALTHY],
    )
