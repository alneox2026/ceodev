# Middleware V2 Architecture

This repository is moving from a function-style middleware to a reusable Cloud Run
gateway plus persistence worker.

## Request path

1. Client calls the public gateway.
2. Gateway verifies Firebase auth.
3. Gateway resolves `agent_id` from server-side config.
4. Gateway calls Agent Runtime.
5. Gateway returns buffered JSON or streams SSE back to the client.
6. Gateway performs a durable Pub/Sub handoff before the final response close.
7. Persistence worker consumes the event and writes Firestore state asynchronously.

## Design rules

- Firestore is not in the hot path for normal chat turns.
- Agent Runtime remains the source of truth for agent execution traces.
- Middleware logs focus on auth, routing, latency, Pub/Sub handoff, and worker
  reliability.
- Legacy `main.py` remains intact until Maxima is cut over safely.

