#!/usr/bin/env bash
# Runs Terraform from this directory with the production tier's secrets:
#
#   ./run.sh plan
#
# .secrets is a gitignored link to matrix-secrets/dotfiles. Its production
# tier's app.env holds the R2 S3 key of the token limited to the state bucket,
# as TF_STATE_ACCESS_KEY_ID and TF_STATE_SECRET_ACCESS_KEY. shared.env, when
# present, loads first, so app.env wins. Terraform alone receives the key, as
# the AWS credentials its S3 backend reads.
#
# The tier's main.tfvars sets the owner, repository, and webhook URL. The
# subcommands that evaluate variables (plan, apply, destroy, refresh, import,
# console) receive it as their first -var-file, so a later -var or -var-file
# wins. Applying a saved plan accepts it while its values match the plan's.
# It holds no token: the GitHub provider's github_access_token variable comes
# from TF_VAR_github_access_token, or Terraform prompts for it.
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

case "${1:-}" in
  plan | apply | destroy | refresh | import | console)
    var_file="$tier_dir/main.tfvars"
    if [[ ! -f "$var_file" ]]; then
      echo "ERROR: $var_file is missing." >&2
      echo "Link .secrets to matrix-secrets/dotfiles; see the Terraform" >&2
      echo "section of docs/provisioning.md." >&2
      exit 1
    fi
    set -- "$1" "-var-file=$var_file" "${@:2}"
    ;;
esac

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
