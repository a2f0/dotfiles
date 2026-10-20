# Overview

Dotfiles and Ansible tasks for package installation / system configuration.

## Developing

Install the tools pinned by `.mise.toml`, then Python dependencies and hooks.
Use the pinned Python on PATH, or activate a virtual environment created by it.

    mise install
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    bun install
    pre-commit install
    pre-commit run --all-files
    python3 -m unittest discover -s tests

Check the shared agent skills (requires Bun)

    bun run agents:check
    bun run test:markdownlint

Agents ship changes with the `ship-pr` skill; see `AGENTS.md`.

For compact output from noisy validation commands, use the pinned harness:

    bun run agent:run --label pre-commit -- pre-commit run --all-files
    bun run agent:run --label preview-tests -- python3 -m unittest discover -s tests
    bun run agent:run --label markdownlint-tests -- bun run test:markdownlint

The harness preserves exit status and full private logs, prints a compact receipt,
and includes a bounded excerpt on failure. Read a log with
`bun run agent-tool logs <log-path>` or search it for required warnings, timings,
and artifacts. Keep review verdicts and other decision output visible; use the
harness for finite commands, not interactive tools or persistent servers.

The markdownlint pre-commit hook uses the Bun-locked local CLI with the same
Markdown file scope and `.markdownlint.yaml` rules. Install Bun dependencies
before running hooks; use the Node version pinned in `.nvmrc` / `.mise.toml`.
CI installs Bun and Node from `.mise.toml` before running the hook.
Python and Ansible retain their existing setup and guarded provisioning checks.

## macOS

Configure via Ansible, after an automatic guarded dry-run:

    ./runAnsible.sh

Preview changes without applying them:

    ./runAnsible.sh --check

Run specific tags in the playbook:

    ./runAnsible.sh --tags 'files'

The wrapper rejects destructive or unsupported changes and preserves existing
configuration files. Reconcile conflicting destinations manually before running
it. See [provisioning](docs/provisioning.md) for guard behavior and isolated tests.

## Ubuntu and Linux Mint

Start from an existing checkout and identify it explicitly; the guard blocks
cloning into an absent checkout:

    ./runAnsible.sh -e "dotfiles_dir=$(pwd) clone_dotfiles=false ansible_python_interpreter=$(command -v python3)"

## Arch Linux

Arch provisioning is blocked because package, reboot, and VM cleanup effects
lack a complete safe preview. Do not bypass the guard with direct playbook or
Vagrant commands. See [provisioning limits](docs/provisioning.md#arch-linux-and-vagrant).

## Maintenance

See [dependency upgrades](docs/dependency-upgrades.md) for upgrade procedures,
active compatibility constraints, security exceptions, and Terraform previews.

Terraform state is in Cloudflare R2. The `terraform/` scripts read its key and
the Terraform variables from the gitignored `.secrets` link to matrix-secrets;
see [Terraform](docs/provisioning.md#terraform).
