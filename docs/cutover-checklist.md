# Maxima Cutover Checklist

Use this checklist immediately before switching FlutterFlow from the legacy middleware to the new gateway.

## Deployment

- gateway image built and pushed
- worker image built and pushed
- Terraform apply completed successfully
- deterministic gateway URL recorded
- Eventarc trigger created successfully
- Cloud Monitoring alert policies created for:
  - gateway 5xx responses
  - elevated gateway p95 latency
  - worker retryable failures

## Runtime validation

- `GET /ready` returns `200`
- buffered smoke test returns `reply_text`
- unauthenticated buffered chat returns `401`
- Pub/Sub publish succeeds on the buffered path
- worker logs show `worker_event_persisted`
- Firestore thread doc is created under `agent_threads/{thread_id}`
- Firestore message docs are created under:
  - `{turn_id}_user`
  - `{turn_id}_assistant`
- archive action returns `status = "archived"` and removes the thread from the active list
- delete action returns `status = "deleted"` and removes the runtime session

## Reliability validation

- duplicate delivery test does not create duplicate message docs
- worker retry path is visible and understood
- gateway still responds if Firestore is temporarily slow, because Firestore is not in the hot path
- Cloud Run Error Reporting remains empty for both services during the launch window
- real browser traffic shows no auth or CORS failures

## Rollback readiness

- legacy `main.py` service URL is still available
- FlutterFlow API config for the legacy service is preserved
- operator has the one-page rollback runbook available
- operator knows how to revert FlutterFlow from the deterministic gateway URL back to the legacy Maxima path

Do not cut over until every item above is explicitly checked.
