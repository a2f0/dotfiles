#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
# The backend is committed in full, so -reconfigure re-reads it and never
# offers to migrate state from a directory initialized for the old S3 bucket.
exec "$script_dir/run.sh" init -input=false -reconfigure
