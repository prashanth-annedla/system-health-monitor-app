

from typing import Dict

from app.dag import get_execution_order, get_direct_dependents
import logging
import networkx as nx
import asyncio
from app.models import HealthStatus
import random

logger = logging.getLogger(__name__)


async def evaluate_health(
        dag: nx.DiGraph,
        health_state: Dict[str, HealthStatus],
) -> None:
    """
    Evaluates the health status of each component in the DAG based on its dependencies.
    The health status is determined as follows:
    - If any dependency is UNHEALTHY, the component is UNHEALTHY.
    - If all dependencies are HEALTHY, the component is HEALTHY.
    - If at least one dependency is DEGRADED and none are UNHEALTHY, the component is DEGRADED.
    
    This function updates the health_state dictionary in-place with the evaluated health status for each component.
    """
    levels = get_execution_order(dag)
    logger.info(f"Starting health evaluation for all components", extra={"evaluation_levels": len(levels)})

    for level_idx, level in enumerate(levels):
        component_ids = list(level)
        logger.info(f"Evaluating health for components at level", extra={"level": level_idx, "components": component_ids},
        )
        #parallelize health checks for all components in the current level since they can be evaluated independently
        healthresults = asyncio.gather(
            *[_stub_health_check(component_id) for component_id in component_ids]
        )

        for component_id, health_status in zip(component_ids, await healthresults):
            health_state[component_id] = health_status
            logger.info(f"Evaluated health for component", extra={"component_id": component_id, "status": health_status})

        _set_healthstatus_dependents(dag, health_state, component_ids)
    
    logger.info(f"Completed health evaluation for all components")


async def _stub_health_check(component_id: str) -> HealthStatus:
    randomnumber = random.randint(1, 100)
    if randomnumber <= 30:
        return HealthStatus.HEALTHY
    elif randomnumber <= 60:
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.UNHEALTHY
    

def _set_healthstatus_dependents(
        dag: nx.DiGraph,
        health_state: Dict[str, HealthStatus],
        evaluated_ids: str,
) -> None:
    for component_id in evaluated_ids:
        if health_state[component_id] == HealthStatus.UNHEALTHY:
            for dependent in get_direct_dependents(dag, component_id):
                if health_state[dependent] != HealthStatus.UNHEALTHY:
                    health_state[dependent] = HealthStatus.DEGRADED
                    logger.info(f"Setting dependent component to DEGRADED due to unhealthy dependency",
                        extra={"component_id": dependent, "unhealthy_parent": component_id}
                    )


async def re_evaluate_dependents(
        dag: nx.DiGraph,
        health_state: Dict[str, HealthStatus],
        component_id: str
) -> None:
    if not nx.descendants(dag, component_id):
        logger.info(f"No dependents to re-evaluate for component", extra={"component_id": component_id})
        return
    logger.info(f"Re-evaluating dependents for component", extra={"component_id": component_id})

    visited = {component_id}
    frontier = {component_id}

    while frontier:
        _set_healthstatus_dependents(dag, health_state, list(frontier))
        next_frontier = set()
        for comp_id in frontier:
            dependents = get_direct_dependents(dag, comp_id)
            for dependent in dependents:
                if dependent not in visited:
                    next_frontier.add(dependent)
                    visited.add(dependent)
        frontier = next_frontier