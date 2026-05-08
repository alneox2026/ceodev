# Middleware V2 API Contract

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
