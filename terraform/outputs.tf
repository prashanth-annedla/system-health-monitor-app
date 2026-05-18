output "pubsub_topic" {
    value = google_pubsub_topic.health_events.name
    description = "Name of the Pub/Sub topic for health events."  
}

output "pubsub_subscription" {
    value = google_pubsub_subscription.health_events_subscription.name
    description = "Name of the Pub/Sub subscription for health events."
}

output "cloud_run_url" {
  value = google_cloud_run_v2_service.application_service.uri
}