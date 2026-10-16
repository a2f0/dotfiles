#!/usr/bin/env bash
# Runs Terraform from this directory with the state bucket's credentials:
#
#   ./run.sh plan -var-file=main.tfvars
#
# .secrets is a gitignored link to matrix-secrets/dotfiles. Its production
# tier's app.env holds the R2 S3 key of the token limited to the state bucket,
# as TF_STATE_ACCESS_KEY_ID and TF_STATE_SECRET_ACCESS_KEY. shared.env, when
# present, loads first, so app.env wins. Terraform alone receives the key, as
# the AWS credentials its S3 backend reads. The GitHub provider still takes its
# token from main.tfvars.
set -euo pipefail

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
tier_dir="$(dirname -- "$script_dir")/.secrets/prod"
cd "$script_dir"

if [[ ! -f "$tier_dir/app.env" ]]; then
  echo "ERROR: $tier_dir/app.env is missing." >&2
  echo "Link .secrets to matrix-secrets/dotfiles; see the Terraform section" >&2
  echo "of docs/provisioning.md." >&2
  exit 1
fi
if [[ -f "$tier_dir/shared.env" ]]; then
  # shellcheck source=/dev/null
  source "$tier_dir/shared.env"
fi
# shellcheck source=/dev/null
source "$tier_dir/app.env"

missing=()
[[ -n "${TF_STATE_ACCESS_KEY_ID:-}" ]] || missing+=("TF_STATE_ACCESS_KEY_ID")
[[ -n "${TF_STATE_SECRET_ACCESS_KEY:-}" ]] ||
  missing+=("TF_STATE_SECRET_ACCESS_KEY")
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "ERROR: Missing Terraform state variables in $tier_dir/app.env:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

# An ambient AWS profile or session token must not redirect the backend or
# pair with the state key.
unset AWS_PROFILE AWS_SESSION_TOKEN
export AWS_ACCESS_KEY_ID="$TF_STATE_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$TF_STATE_SECRET_ACCESS_KEY"
exec terraform "$@"
