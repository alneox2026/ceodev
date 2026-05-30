# Maxima Cloud Run Canary

`maxima_cloudrun` is a separate ADK canary project for validating Maxima on Cloud Run without changing the production Agent Runtime deployment.

The canary keeps Maxima's current instructions and Google Search grounding behavior, but defaults to `gemini-3-flash-preview`. It is intended to be deployed as a private Cloud Run service named `maxima-cloudrun-canary` and called only through `ceoagent-gateway`.

Gemini 3 Flash is currently exposed on Vertex AI as `gemini-3-flash-preview` and uses the `global` model location. Keep the Cloud Run service in `us-central1`, but deploy with `GOOGLE_CLOUD_LOCATION=global` for model calls.

When deployed through `agents-cli`, the ADK API server exposes the app as `app` because the configured `agent_directory` is `app`. The ADK `App(name=...)` and gateway registry `app_name` must therefore both be `app` unless the deployment package layout is changed.

For production Cloud Run use, replace the in-memory ADK session backend with a persistent session backend before sending real user traffic directly to this service.
