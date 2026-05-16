# system-health-monitor-app
This is an Python application that evaluates the health of a distributed system

# Assumptions

Messaging: For local testing, used asycio.Queue, in real world, we can use GCP Pub/Sub
Health Status Outputs: healthy, degraded, unhealthy
- If parent is unhealthy, all child nodes will become degraded
DAG Traversal: 
- networkx.topological_generatons() returns node level in BFS order.
Storage: in-memory Python dict

