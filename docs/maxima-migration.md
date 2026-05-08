# Maxima Migration Plan

## Current state

- `main.py` is the working legacy middleware.
- FlutterFlow currently uses the legacy path.

## Target state

- `services/agent_gateway` becomes the public middleware.
- `services/agent_persistence_worker` consumes Pub/Sub events and writes Firestore.

## Cutover rule

Do not cut Maxima over until:

1. buffered gateway path is implemented
2. streaming path is implemented
3. Pub/Sub handoff is implemented
4. worker persistence is implemented
5. smoke tests pass
6. rollback path is documented and preserved

Status in this repo:

- items 1 through 4 are now implemented in code
- local unit/integration tests are passing
- deployment, live smoke testing, and FlutterFlow cutover remain pending
