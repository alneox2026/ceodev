# Maxima Rollback Runbook

Use this runbook if the new Cloud Run gateway must be rolled back after Maxima has been cut over in FlutterFlow.

## Trigger conditions

Rollback immediately if any of the following are true:

- gateway returns repeated 5xx responses to real user traffic
- Cloud Run Error Reporting opens incidents for the gateway or worker
- worker retries are repeating and delete/persist lifecycle is stuck
- browser traffic shows auth or CORS failures that block normal use
- Firestore thread lifecycle becomes inconsistent under real load

## 1. Freeze further user changes

1. Stop making new FlutterFlow changes.
2. Keep the current production build as-is until the rollback is complete.

## 2. Revert FlutterFlow API configuration

1. Open the Maxima API configuration in FlutterFlow.
2. Replace the current gateway base URL:

```text
https://ceoagent-gateway-281577273798.us-central1.run.app
```

3. Restore the preserved legacy Maxima endpoint configuration from `main.py`.
4. Publish the reverted FlutterFlow build.

## 3. Verify legacy health

Confirm the legacy service still responds:

- `GET /health` returns `200`

Then run one real authenticated smoke turn through the legacy path and confirm:

- the request succeeds
- the assistant reply is returned
- the browser shows no auth or CORS issue

## 4. Verify user-facing recovery

Confirm from the real app:

- new chat works again
- existing chat continuation works again
- no browser auth/CORS errors appear

## 5. Preserve evidence

Before changing the backend further, capture:

- gateway Cloud Run logs during the failure window
- worker Cloud Run logs during the failure window
- any Error Reporting incidents
- the affected `thread_id` and `session_id` examples from Firestore

## 6. Do not do during rollback

- do not delete Firestore thread or message docs manually
- do not delete Agent Runtime sessions manually as part of rollback
- do not change the worker trigger unless the failure is trigger-specific

## 7. Recovery path after rollback

After users are stable on the legacy path:

1. diagnose the new gateway/worker issue
2. fix it in the repo
3. redeploy to Cloud Run
4. re-run buffered smoke tests and lifecycle validation
5. cut over again only after the issue is explicitly verified as fixed
