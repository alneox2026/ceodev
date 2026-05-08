# Maxima Cutover Checklist

Use this checklist immediately before switching FlutterFlow from the legacy middleware to the new gateway.

## Deployment

- gateway image built and pushed
- worker image built and pushed
- Terraform apply completed successfully
- gateway URL recorded
- Eventarc trigger created successfully

## Runtime validation

- buffered smoke test returns `reply_text`
- streaming smoke test emits `metadata`, `token`, and final `done`
- Pub/Sub publish succeeds on both buffered and streaming paths
- worker logs show `worker_event_persisted`
- Firestore thread doc is created under `agent_threads/{thread_id}`
- Firestore message docs are created under:
  - `{turn_id}_user`
  - `{turn_id}_assistant`

## Reliability validation

- duplicate delivery test does not create duplicate message docs
- worker retry path is visible and understood
- gateway still responds if Firestore is temporarily slow, because Firestore is not in the hot path

## Rollback readiness

- legacy `main.py` service URL is still available
- FlutterFlow API config for the legacy service is preserved
- operator knows how to revert the gateway URL in FlutterFlow

Do not cut over until every item above is explicitly checked.
