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
  "reply_text": "...",
  "usage": {}
}
```

When the backend returns Gemini usage metadata, `usage` preserves the raw metadata and adds:

- `token_counts`
- `billable_tokens`
- `pricing_model: "gemini-2.5-flash"`
- `pricing_unit: "usd_per_1m_tokens"`
- `pricing`
- `estimated_cost_usd`
- `estimated_cost_breakdown_usd`

Pricing basis:

- input text/image/video: `$0.30` per 1M tokens
- input audio: `$1.00` per 1M tokens
- output including thinking tokens: `$2.50` per 1M tokens

If the backend only returns an unsplit `total_token_count`, the gateway preserves the count but does not emit cost fields.

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
