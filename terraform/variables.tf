variable "project_id" {
    type = string
}

variable "region" {
    description = "GCP region to deploy the resources"
    type = string
    default = "us-central1"
}

variable "image" {
    description = "Docker image URL"
    type = string
}