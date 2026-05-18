terraform{
    required_providers {
        google = {
            source = "hashicorp/google"
            version = "~> 5.0"
        }
    }
}

provider "google" {
    project = var.project_id
    region = var.region
}

resource "google_pubsub_topic" "health_events" {
    name = "health-events"
}

resource "google_pubsub_subscription" "health_events_subscription" {
    name  = "health-events-subscription"
    topic = google_pubsub_topic.health_events.name
}

resource "google_artifact_registry_repository" "application_repository" {
    location = var.region
    repository_id = "system-health-monitor-app"
    format   = "DOCKER"
}

resource "google_cloud_run_v2_service" "application_service" {
    name     = "system-health-monitor-app"
    location = var.region

    template {
        containers {
            image = var.image
            
            env {
                name = "EVENT_BACKEND"
                value = "pubsub"
            }

            env {
                name = "PUBSUB_PROJECT_ID"
                value = var.project_id
            }

            env {
                name = "PUBSUB_SUBSCRIPTION"
                value = "health-events-subscription"
            }
        }
    }  
}

resource "google_cloud_run_v2_service_iam_member" "application_service_invoker" {
    project = var.project_id
    name = google_cloud_run_v2_service.application_service.name
    location = var.region
    role = "roles/run.invoker"
    member = "allUsers"
}