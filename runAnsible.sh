#!/bin/sh

set -eu

INVENTORY="ansible/inventory.yaml"
LIMIT_HOST="127.0.0.1"

detect_playbook() {
  os_name="$(uname -s)"

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

exec ansible-playbook -i "$INVENTORY" "$playbook" -l "$LIMIT_HOST" "$@"
