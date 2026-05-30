# Maxima Cloud Run Canary

`maxima_cloudrun` is a separate ADK canary project for validating Maxima on Cloud Run without changing the production Agent Runtime deployment.

The canary keeps Maxima's current instructions and Google Search grounding behavior, but defaults to `gemini-3.5-flash`. It is intended to be deployed as a private Cloud Run service named `maxima-cloudrun-canary` and called only through `ceoagent-gateway`.

When deployed through `agents-cli`, the ADK API server exposes the app as `app` because the configured `agent_directory` is `app`. Gateway registry `app_name` must therefore be `app` unless the deployment command is changed to expose a different ADK app name.

For production Cloud Run use, replace the in-memory ADK session backend with a persistent session backend before sending real user traffic directly to this service.
