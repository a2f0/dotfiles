#!/bin/sh

set -eu

detect_playbook() {
  os_name="$(/usr/bin/uname -s)"

  case "$os_name" in
    Darwin)
      echo "ansible/playbook-macos.yaml"
      return 0
      ;;
    Linux)
      if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release

        case "${ID:-}" in
          ubuntu)
            echo "ansible/playbook-ubuntu-linux.yaml"
            return 0
            ;;
          arch)
            echo "ansible/playbook-arch-linux.yaml"
            return 0
            ;;
        esac

        case "${ID_LIKE:-}" in
          *ubuntu*|*debian*)
            echo "ansible/playbook-ubuntu-linux.yaml"
            return 0
            ;;
          *arch*)
            echo "ansible/playbook-arch-linux.yaml"
            return 0
            ;;
        esac
      fi
      ;;
  esac

  echo "Unsupported environment: unable to map host to a known playbook." >&2
  echo "Detected platform: uname=$os_name ID=${ID:-unknown} ID_LIKE=${ID_LIKE:-unknown}" >&2
  exit 1
}

playbook="$(detect_playbook)"

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
cd "$script_dir"

if [ ! -x .venv/bin/python3 ]; then
  echo "Creating Python environment in $script_dir/.venv" >&2
  python3 -I -m venv .venv
fi

echo "Ensuring Python dependencies in $script_dir/.venv" >&2
"$script_dir/.venv/bin/python3" -I -m pip --require-virtualenv install \
  --disable-pip-version-check --quiet -r requirements.txt

exec "$script_dir/.venv/bin/python3" -I scripts/deploy/ansible_safe_run.py "$playbook" "$@"
