from typing import Dict, List, Set
import networkx as nx
from app.models import ComponentInput


class ComponentNotFoundError(ValueError):
    pass


class CycleDetectedError(ValueError):
    pass


def create_dag(Components: List[ComponentInput]) -> nx.DiGraph:
    dagGraph = nx.DiGraph()

    # Adding all the components as nodes in the DAG
    for component in Components:
        dagGraph.add_node(component.id, name=component.name)

    known_ids: Set[str] = {component.id for component in Components}

    for component in Components:
        for id in component.dependencies:
            if id not in known_ids:
                raise ComponentNotFoundError(
                    f"Component {component.id} has an unknown dependency: {id}"
                )
            dagGraph.add_edge(id, component.id)

    if not nx.is_directed_acyclic_graph(dagGraph):
        raise CycleDetectedError(
            "The provided components contain circular dependencies, which is not allowed in a DAG."
        )

    return dagGraph


def get_execution_order(dagGraph: nx.DiGraph) -> List[str]:
    return list(nx.topological_generations(dagGraph))


def get_dag_summary(dagGraph: nx.DiGraph) -> Dict:
    return {
        "component_count": dagGraph.number_of_nodes(),
        "dependency_count": dagGraph.number_of_edges(),
        "evaluation_levels": len(get_execution_order(dagGraph)),
        "components": list(dagGraph.nodes),
    }


def get_dependencies(dagGraph: nx.DiGraph, component_id: str) -> List[str]:
    return list(dagGraph.predecessors(component_id))


def get_direct_dependents(dagGraph: nx.DiGraph, component_id: str) -> Set[str]:
    return set(dagGraph.successors(component_id))
