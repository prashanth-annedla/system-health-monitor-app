import pytest
from app.dag import create_dag, ComponentNotFoundError, CycleDetectedError, get_execution_order
from app.models import ComponentInput


def test_create_dag_valid():
    components = [
        ComponentInput(id="dbservice", name="Database Service", dependencies=[]),
        ComponentInput(id="authservice", name="Authentication Service", dependencies=[]),
        ComponentInput(id="apiservice", name="API Service", dependencies=["authservice", "dbservice"]),
        ComponentInput(id="frontend", name="Frontend Service", dependencies=["apiservice"]),
    ]

    dag = create_dag(components)

    assert dag.number_of_nodes() == 4
    assert dag.number_of_edges() == 3
    assert list(dag.nodes) == ["dbservice", "authservice", "apiservice", "frontend"]

    execution_order = get_execution_order(dag)
    assert len(execution_order) == 3
    assert set(execution_order[0]) == {"dbservice", "authservice"}
    assert set(execution_order[1]) == {"apiservice"}
    assert set(execution_order[2]) == {"frontend"}


def test_create_dag_unknown_dependency():
    components = [
        ComponentInput(id="apiservice", name="API Service", dependencies=["missing-service"]),
    ]

    with pytest.raises(ComponentNotFoundError):
        create_dag(components)


def test_create_dag_cycle_detection():
    components = [
        ComponentInput(id="a", name="A", dependencies=["b"]),
        ComponentInput(id="b", name="B", dependencies=["a"]),
    ]

    with pytest.raises(CycleDetectedError):
        create_dag(components)
