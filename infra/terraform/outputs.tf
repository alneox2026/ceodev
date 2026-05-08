output "gateway_url" {
  value       = google_cloud_run_v2_service.gateway.uri
  description = "Public URL for the gateway service."
}

output "worker_url" {
  value       = google_cloud_run_v2_service.worker.uri
  description = "Authenticated URL for the persistence worker."
}

output "gateway_service_account_email" {
  value       = google_service_account.gateway.email
  description = "Gateway runtime service account email."
}

output "worker_service_account_email" {
  value       = google_service_account.worker.email
  description = "Worker runtime service account email."
}

output "eventarc_service_account_email" {
  value       = google_service_account.eventarc.email
  description = "Eventarc trigger service account email."
}

output "agent_turn_events_topic" {
  value       = google_pubsub_topic.agent_turn_events.id
  description = "Pub/Sub topic id for completed turn events."
}

output "eventarc_trigger_name" {
  value       = google_eventarc_trigger.worker_turn_events.name
  description = "Eventarc trigger name for worker delivery."
}
