from fastapi.testclient import TestClient
import pytest
import app.main as main_module
from app.models import HealthStatus


@pytest.fixture(autouse=True)
def reset_app_state():
    main_module.dag = None
    main_module.componenent_registry = {}
    main_module.health_status = {}
    yield


def test_register_component_endpoint(monkeypatch):
    async def fake_evaluate_health(dag, health_status):
        return None

    monkeypatch.setattr(main_module, "evaluate_health", fake_evaluate_health)
    client = TestClient(main_module.app)

    payload = {
        "components": [
            {"id": "dbservice", "name": "Database Service", "dependencies": []},
            {"id": "authservice", "name": "Authentication Service", "dependencies": []},
            {"id": "apiservice", "name": "API Service", "dependencies": ["authservice", "dbservice"]},
            {"id": "frontend", "name": "Frontend Service", "dependencies": ["apiservice"]},
        ]
    }

    response = client.post("/register_component", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["component_count"] == 4
    assert body["evaluation_levels"] == 3
    assert body["message"].startswith("Component(s) registered successfully")


def test_update_metrics_endpoint(monkeypatch):
    async def fake_evaluate_health(dag, health_status):
        return None

    monkeypatch.setattr(main_module, "evaluate_health", fake_evaluate_health)
    client = TestClient(main_module.app)

    register_payload = {
        "components": [
            {"id": "dbservice", "name": "Database Service", "dependencies": []},
            {"id": "authservice", "name": "Authentication Service", "dependencies": []},
            {"id": "apiservice", "name": "API Service", "dependencies": ["authservice", "dbservice"]},
        ]
    }

    register_response = client.post("/register_component", json=register_payload)
    assert register_response.status_code == 201

    event_payload = {
        "component_id": "dbservice",
        "status": "unhealthy",
        "details": "Database connection timeout"
    }

    response = client.post("/update-metrics", json=event_payload)
    assert response.status_code == 201
    assert response.json()["accepted"] is True
    assert response.json()["component_id"] == "dbservice"
    assert response.json()["new_status"] == "unhealthy"
