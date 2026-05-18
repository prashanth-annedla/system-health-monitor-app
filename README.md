# System Health Monitor

A Python-based system that evaluates the health of distributed system composed of multiple dependent components modelled as a DAG (Directed Acyclic Graph). Supports request driven and event-driven health updates.

---

## Table of Contents

- [Features Implemented](#features-implemented)
- [Architecture Overview](#architecture-overview)
- [How the DAG is Modelled and Traversed](#how-the-dag-is-modelled-and-traversed)
- [Async Health Evaluation](#async-health-evaluation)
- [Event-Driven Health Updates](#event-driven-health-updates)
- [How to Run Locally](#how-to-run-locally)
- [API Reference](#api-reference)
- [Observability](#observability)
- [Infrastructure as Code (IaC)](#infrastructure-as-code-iac)
- [CI/CD Pipeline](#cicd-pipeline)
- [Assumptions](#assumptions)
- [Features Intentionally Excluded](#features-intentionally-excluded)
- [Design Trade-offs](#design-trade-offs)
- [AI Tool Usage](#ai-tool-usage)

---

## Features Implemented

- **FastAPI web API** - Accepts JSON payload describing components and their dependencies
- **DAG construction and cycle detection** - built with `networkx`. Rejects invalid inputs (unknown dependencies, circular depdencies)
- **BFS ordered async health evaluation** - Components are evaluated level by level using `topological_generations()`. Components within the same level are evaluated concurrently with `asyncio.gather`
- **Dependency health propagation** - When a component is `unhealthy`, it's direct and transitive dependents are automatically marked as `degraded`
- **Event-driven health updates** - A background consumer loop reads from an event bus and applies changes
- **Component Health Status** - `GET /components-status` returns overall system health, per-component status sorted by severity and counts
- **Prometheus metrics** - exposed at `/metrics` via `prometheus-fastapi-instrumentor`
- **Structured JSON logging** - used `structlog`
- **Distributed tracing** - used OpenTelemetry for tracing
- **Observability** - `GET /health` for health checks
- **Dockerfile** - container image for deployment
- **Terraform IaC** - Sample Terraform Code for GCP. *Not tested*
- **GitHub Actions CI/CD** - Build, Test and Deploy jobs

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI App                                     │
│                                                                              │
│  POST /register-components                                                   │
│            │                                                                 │
│            ▼                                                                 │
│     ┌─────────────────────┐                                                  │
│     │     DAG Builder     │                                                  │
│     │      (networkx)     │                                                  │
│     └─────────────────────┘                                                  │
│                 │                                                            │
│                 ▼                                                            │
│     ┌─────────────────────┐                                                  │
│     │     BFS Levels      │                                                  │
│     │ (topological gens)  │                                                  │
│     └─────────────────────┘                                                  │
│                 │                                                            │
│                 ▼                                                            │
│     ┌─────────────────────┐         ┌─────────────────────┐                  │
│     │  Health Status Dict │ ◄────── │    Event Consumer   │                  │
│     └─────────────────────┘         └─────────────────────┘                  │
│                 │                              ▲                             │
│                 ▼                              │                             │
│     ┌─────────────────────┐         ┌─────────────────────┐                  │
│     │       Summary       │         │    asyncio.Queue    │                  │
│     └─────────────────────┘         └─────────────────────┘                  │
│                 │                              ▲                             │
│                 ▼                              │                             │
│      GET /components-status                    │                             │
│                                                │                             │
│      POST /update-metrics ─────────────────────┘                             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```
**Storage** - In-memory Python dicts (`register-components`, `components-status`)

---

## How the DAG is Modelled and Traversed

Components and their dependencies are stored as a `networkx.DiGraph`. A directed edge `A -> B` means "B depends on A" (A must be healthy for B to be healthy).

On Registration:
1. All component IDs are added as nodes.
2. Dependency edges are validated

For traversal, `nx.topological_generations()` is used. This gives sets of nodes where all nodes in a set have no unresolved predecessors which is equivalent to BFS level ordering. 

---

## Async Health Evaluation

health evaluation is triggered as a FastAPI `BackgroundTask` after every `POST /register-components`.

1. The graph is split into topological levels.
2. For each level, `asyncio.gather` fires all health check concurrently.
3. A stub health check is used which produces a random result

---

## Event-Driven Health Updates

A persistent background `asyncio.Task` runs `event_bus.consume()` for the lifetime of the application. 

on each event,

1. The components status in `health_state` is updated immediately.
2. `re_evaluate_dependents` performs a BFS from the changed component, propagating `degraded` state to all the transitive dependents.
3. The overall health can be reflected using `GET /components-status`

## How to Run Locally

**Prerequisites:**

- Python 3.12+ (use a virtualenv)
- Build dependencies from `requirements.txt`.
- Docker

Quick start:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app
```

Once above commands are executed, browse the interactive API docs at: http://localhost:8000/docs

Run tests:

```bash
python -m pytest -q
```

Or with Docker:

```bash
docker build -t system-health-monitor-app .
docker run -p 8000:8000 system-health-monitor-app
```

### Register components and check health

```bash
#1. Register Components
curl -X POST http://localhost:8000/register-components \
    -H "Content-Type: application/json" \
    -d '{
        "components": [
            { "id": "dbservice", "name": "Database Service","dependencies": [] },
            { "id": "authservice", "name": "Authentication Service","dependencies": [] },
            { "id": "apiservice", "name": "API Service","dependencies": ["authservice", "dbservice"] },
            { "id": "frontend", "name": "Frontend Service","dependencies": ["apiservice"] }
        ]
    }'

#2. Check components health
curl http://localhost:8000/components-status

#3. Simulate a health event
curl -X POST http://localhost:8000/update-metrics \
    -H "Content-Type: application/json" \
    -d '{
        "component_id": "dbservice",
        "status": "unhealthy",
        "details": "Database connection timeout"
    }'
```
---

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/register-components` | Register components and trigger health evaluation |
| `GET` | `/components-status` | Get components health status | 
| `POST` | `/update-metrics` | Inject health event | 
| `GET` | `/health` | Health check of the application | 
| `GET` | `/metrics` | Prometheus metrics | 
| `GET` | `/docs` | Interactive swagger UI | 

---

## Observability

| Signal | Implementation |
|---|---|
| **Logging** | `structlog` - structured JSON logs with log level and timestamp |
| **Metrics** | `prometheus-fastapi-instrumentation` - request count, latency, and status codes at `/metrics` |
| **Tracing** | OpenTelemetry SDK |
| **Health endpoint** | `Get /health` returns `{"status": "ok"}` - can be used for application health check status |

---

## Infrastructure as Code (IaC)

- Sample terraform code to connect and serverless deployment in GCP. *Not Tested*

---

## CI/CD Pipeline

- A CI pipeline to build the docker image. *Tested*
- A CD pipeline for deploy to GCP. *Not Tested*

---

## Assumptions

- **Messaging** - `asyncio.Queue` is used as the local event bus. We can use something like GCP pub/sub in real world application.
- **Component Health checks** - `_stub_health_check` returns random status. In real world applications, we can hit the actual endpoints and get the status.
- **Dependency Nodes Health** - In parent is `unhealthy`, all direct children becomes degraded. In real world, it depends on application requirement.
- **Storage** - In-memory dicts. Re-registering components overwrites the previous state as random statuses are being calculated.

---

## Features Intentionally Excluded

- **persistence / database** - In-memory state is enough to test the application. Adding database would make this complex and not much useful for the excerise.
- **Authentication / authorization** - Out of scope. For production application, we can use API keys.
- **Component Health Checks** - Stub component health checks, Production application would call the actual application health check endpoints.

---

## Design Trade-offs

- `asyncio.Queue` as event bus since it has not other external dependencies and easy to test locally. It's not durable since events are lost on restart and cannot be share in multi instance scenario.
- In memory state dicts - Fast reads, no external dependencies. State is lost on restarts.
- Stub health checks - good for local testing without real infrastructure.

---

## AI Tool Usage

Github Copilot (Claude Haiku 4.5) was used for development

- Scaffold FastAPI route handlers, Pydantic models, and async patterns.
- Generating the `re-evaluate-dependents` BFS logic
- Drafting terraform code.
- Creating the tests
- Generated partial content of README file.