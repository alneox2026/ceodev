# Pub/Sub Event Schema

The gateway publishes one normalized event for each completed turn.

## Event type

`agent.turn.completed`

## Required fields

- `event_id`
- `turn_id`
- `agent_id`
- `user_id`
- `thread_id`
- `session_id`
- `user_message`
- `assistant_message`
- `created_at`

## Delivery model

- Pub/Sub is at-least-once delivery.
- The persistence worker must be idempotent.
- Deterministic message document IDs are used for persistence:
  - `{turn_id}_user`
  - `{turn_id}_assistant`
