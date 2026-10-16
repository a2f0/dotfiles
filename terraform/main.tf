# State lives in the Cloudflare R2 bucket dotfiles-terraform-state
# (S3-compatible). run.sh hands the bucket token's R2 S3 key from
# .secrets/prod/app.env to Terraform as the AWS credentials the backend reads.
terraform {
  # use_lockfile needs Terraform 1.10 or later.
  required_version = ">= 1.10"

  backend "s3" {
    bucket = "dotfiles-terraform-state"
    key    = "terraform.tfstate"
    region = "auto"
    endpoints = {
      s3 = "https://0be508e6c4caa573595c5f94e11900e4.r2.cloudflarestorage.com"
    }
    use_lockfile                = true
    use_path_style              = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
  }

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
