# Middleware V2 Deployment Runbook

This runbook covers the first live deployment of the new middleware stack:

- public Cloud Run gateway
- authenticated Cloud Run persistence worker
- Pub/Sub topic for completed turn events
- Eventarc trigger from Pub/Sub to the worker

## 1. Build and push container images

Preferred path:

```powershell
.\scripts\build_images.ps1
```

Manual equivalent:

```bash
docker build -f services/agent_gateway/Dockerfile -t us-central1-docker.pkg.dev/ceo-dev123/ceosystem/ceoagent-gateway:latest .
docker push us-central1-docker.pkg.dev/ceo-dev123/ceosystem/ceoagent-gateway:latest
docker build -f services/agent_persistence_worker/Dockerfile -t us-central1-docker.pkg.dev/ceo-dev123/ceosystem/ceoagent-persistence-worker:latest .
docker push us-central1-docker.pkg.dev/ceo-dev123/ceosystem/ceoagent-persistence-worker:latest
```

## 2. Prepare Terraform variables

Copy [terraform.tfvars.example](/c:/Users/Admin/Desktop/CEOsystem-dev3/infra/terraform/terraform.tfvars.example) to `terraform.tfvars` and fill in the real image URIs and allowed frontend origins.

## 3. Apply infrastructure

Preferred path:

```powershell
.\scripts\deploy_infra.ps1 `
  -GatewayImage "us-central1-docker.pkg.dev/ceo-dev123/ceosystem/ceoagent-gateway:latest" `
  -WorkerImage "us-central1-docker.pkg.dev/ceo-dev123/ceosystem/ceoagent-persistence-worker:latest" `
  -AllowedOrigins "https://your-flutterflow-domain.example"
```

Manual equivalent from [infra/terraform](/c:/Users/Admin/Desktop/CEOsystem-dev3/infra/terraform):

```bash
terraform init
terraform plan
terraform apply
```

This Terraform stack creates:

- the gateway Cloud Run service
- the worker Cloud Run service
- service accounts with least-privilege runtime roles
- the `agent-turn-events` Pub/Sub topic
- the Eventarc trigger that invokes the worker on `/events/pubsub`

## 4. Smoke test the gateway

Use [smoke_gateway.ps1](/c:/Users/Admin/Desktop/CEOsystem-dev3/scripts/smoke_gateway.ps1).

Full rollout helper:

```powershell
.\scripts\rollout_maxima.ps1 `
  -AuthToken "FIREBASE_ID_TOKEN" `
  -AllowedOrigins "https://your-flutterflow-domain.example"
```

Buffered test:

```powershell
.\scripts\smoke_gateway.ps1 `
  -ServiceUrl "https://YOUR_GATEWAY_URL" `
  -AuthToken "FIREBASE_ID_TOKEN" `
  -Message "Hello from the new gateway"
```

Streaming test:

```powershell
.\scripts\smoke_gateway.ps1 `
  -ServiceUrl "https://YOUR_GATEWAY_URL" `
  -AuthToken "FIREBASE_ID_TOKEN" `
  -Message "Hello from the new streaming gateway" `
  -Stream
```

## 5. Verify the full path

Confirm all of the following:

1. gateway returns `reply_text` for buffered chat
2. stream emits `metadata`, `token`, and final `done`
3. Pub/Sub topic receives events
4. worker logs show `worker_event_persisted`
5. Firestore receives:
   - `agent_threads/{thread_id}`
   - `agent_threads/{thread_id}/messages/{turn_id}_user`
   - `agent_threads/{thread_id}/messages/{turn_id}_assistant`

## 6. Cutover rule

Do not switch FlutterFlow to the new gateway until:

1. buffered smoke test passes
2. streaming smoke test passes
3. worker persistence is visible in Firestore
4. duplicate delivery test confirms no duplicate messages
5. rollback path to the legacy `main.py` service remains available

## 7. Script inventory

- [build_images.ps1](/c:/Users/Admin/Desktop/CEOsystem-dev3/scripts/build_images.ps1): build and push both container images
- [deploy_infra.ps1](/c:/Users/Admin/Desktop/CEOsystem-dev3/scripts/deploy_infra.ps1): write Terraform vars, run `init`, `plan`, and optionally `apply`
- [rollout_maxima.ps1](/c:/Users/Admin/Desktop/CEOsystem-dev3/scripts/rollout_maxima.ps1): build, deploy, fetch gateway URL, and run buffered/stream smoke tests
- [smoke_gateway.ps1](/c:/Users/Admin/Desktop/CEOsystem-dev3/scripts/smoke_gateway.ps1): direct buffered or stream call against an existing gateway URL

## Sources

- ADK Agent Runtime testing guide: [adk.dev/deploy/agent-runtime/test](https://adk.dev/deploy/agent-runtime/test/)
- Cloud Run service identity: [cloud.google.com/run/docs/configuring/services/service-identity](https://cloud.google.com/run/docs/configuring/services/service-identity)
- Eventarc Pub/Sub to Cloud Run Terraform: [cloud.google.com/eventarc/standard/docs/run/create-trigger-pub-sub-terraform](https://cloud.google.com/eventarc/standard/docs/run/create-trigger-pub-sub-terraform)
- Pub/Sub publisher roles: [cloud.google.com/pubsub/docs/publisher](https://cloud.google.com/pubsub/docs/publisher)
