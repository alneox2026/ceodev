# Middleware V2 API Contract

## Service probes

- `GET /health`
- `GET /ready`

Use `/ready` as the Cloud Run probe target and operational readiness check.

## Buffered chat

`POST /v1/agents/{agent_id}/chat`

Request body:

```json
{
  "message": "Hello",
  "thread_id": "thread-optional",
  "session_id": "session-optional",
  "client_turn_id": "turn-optional",
  "metadata": {}
}
```

Success response target shape:

```json
{
  "ok": true,
  "agent_id": "maxima",
  "thread_id": "thread-...",
  "session_id": "session-...",
  "turn_id": "turn-...",
  "reply_text": "..."
}
```

## Streaming chat

`POST /v1/agents/{agent_id}/chat/stream`

Launch posture for Maxima:

- keep this endpoint deployed and validated server-side
- do not wire it into FlutterFlow until after the buffered launch is stable

SSE event names:
- `metadata`
- `token`
- `done`
- `error`

Current stream contract:

- `metadata` includes `request_id`, `turn_id`, `agent_id`, `thread_id`, and `session_id`
- `token` includes `{"text": "..."}` fragments normalized from Agent Runtime events
- `done` includes the assembled `reply_text`, `usage`, and `pubsub_message_id` when persistence is enabled
- `error` includes a structured `code`, `message`, and `details`

Durability rule:

- For buffered chat, Pub/Sub publish happens before the JSON response is returned.
- For streaming chat, Pub/Sub publish happens after the last upstream token is assembled and before the final `done` event is emitted.
