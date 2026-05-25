locals {
  enabled_apis = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "eventarc.googleapis.com",
    "firestore.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  gateway_env = {
    GOOGLE_CLOUD_PROJECT             = var.project_id
    GOOGLE_CLOUD_REGION              = var.region
    AGENT_REGISTRY_PATH              = var.agent_registry_path
    AGENT_TURN_EVENTS_TOPIC          = var.pubsub_topic_name
    FIRESTORE_THREADS_COLLECTION     = var.firestore_threads_collection
    PUBSUB_PUBLISH_TIMEOUT_SECONDS   = tostring(var.pubsub_publish_timeout_seconds)
    REQUIRE_FIREBASE_AUTH            = tostring(var.require_firebase_auth)
    ALLOWED_ORIGINS                  = join(",", var.allowed_origins)
    GATEWAY_LOG_LEVEL                = var.gateway_log_level
    GATEWAY_STREAM_DEBUG             = tostring(var.gateway_stream_debug)
    UPSTREAM_CONNECT_TIMEOUT_SECONDS = tostring(var.upstream_connect_timeout_seconds)
    UPSTREAM_READ_TIMEOUT_SECONDS    = tostring(var.upstream_read_timeout_seconds)
  }

  worker_env = {
    GOOGLE_CLOUD_PROJECT                    = var.project_id
    WORKER_LOG_LEVEL                        = var.worker_log_level
    FIRESTORE_THREADS_COLLECTION            = var.firestore_threads_collection
    FIRESTORE_MESSAGES_SUBCOLLECTION        = var.firestore_messages_subcollection
    FIRESTORE_IDEMPOTENCY_COLLECTION        = var.firestore_idempotency_collection
    RUNTIME_DELETE_TIMEOUT_SECONDS          = tostring(var.runtime_delete_timeout_seconds)
    WORKER_REQUIRE_EVENTARC_AUTH            = tostring(var.worker_require_eventarc_auth)
    WORKER_EVENTARC_ALLOWED_SERVICE_ACCOUNT = var.worker_eventarc_allowed_service_account != "" ? var.worker_eventarc_allowed_service_account : google_service_account.eventarc.email
    WORKER_EVENTARC_AUDIENCE                = var.worker_eventarc_audience
  }
}
