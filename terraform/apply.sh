#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
# run.sh supplies .secrets/prod/main.tfvars.
exec "$script_dir/run.sh" apply
