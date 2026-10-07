terraform {
  backend "s3" {}

  required_providers {
    github = {
      source  = "integrations/github"
      version = "6.13.0"
    }
  }
}

provider "github" {
  token = var.github_access_token
  owner = var.github_owner
}

resource "github_actions_secret" "slack_webhook_url" {
  repository  = var.github_repository
  secret_name = "SLACK_WEBHOOK_URL"
  value       = var.slack_webhook_url
}
