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
- live deployment and smoke testing are complete
- FlutterFlow cutover remains pending

## FlutterFlow endpoint switch

Update the Maxima API configuration in FlutterFlow to point to the new gateway base URL:

```text
https://ceoagent-gateway-xpsx2h45iq-uc.a.run.app
```

Use these endpoints:

- buffered: `POST /v1/agents/maxima/chat`
- streaming: `POST /v1/agents/maxima/chat/stream`

Send the Firebase ID token in the `Authorization` header:

```text
Authorization: Bearer <firebase_id_token>
```

Buffered request body:

```json
{
  "message": "Hello",
  "thread_id": "thread-optional",
  "session_id": "session-optional"
}
```

Persist and reuse `thread_id` and `session_id` from the first successful response for follow-up turns.
