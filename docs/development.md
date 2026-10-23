# Development and repository layout

Read [normal setup and usage](../README.md) before working on the configuration.
The [provisioning guide](provisioning.md) owns preview limits and operational
procedures; [AGENTS.md](../AGENTS.md) owns branch, review, and shipping policy.

## Setup and installation

```bash
# Install the pinned tools, Python dependencies, and pre-commit hooks
mise install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pre-commit install

# Install agent tooling and the local markdownlint hook (requires Bun)
bun install

# Install system dependencies for linting
brew install shellcheck luacheck  # macOS
# Linux: install via luarocks since luacheck isn't in apt repositories
sudo apt-get install shellcheck lua5.3 lua5.3-dev luarocks
sudo luarocks install luacheck
```

## Validation

```bash
# Run all pre-commit hooks on all files
bun run agent:run --label pre-commit -- pre-commit run --all-files

# Run specific pre-commit hook
pre-commit run shellcheck
pre-commit run luacheck
pre-commit run check-yaml

# Check that the shared agent skills are current
bun run agents:check

# Verify the Ansible preview safety gate
bun run agent:run --label preview-tests -- python3 -m unittest discover -s tests
bun run agent:run --label markdownlint-tests -- bun run test:markdownlint
```

Use `bun run agent:run --label <name> -- <command> [args...]` for noisy finite
commands. It preserves the command's exit status and full private logs while
returning a compact receipt and a bounded failure excerpt. Inspect required
warnings, timings, and artifacts before accepting a check; use
`bun run agent-tool logs <log-path>` or a targeted search for more evidence.
Keep review verdicts and structured decision output visible. Do not wrap
interactive tools or persistent servers. Existing hooks and CI checks still run
normally.

## Architecture

### Core Structure

- **`ansible/`** - Contains all Ansible playbooks, inventory, and tasks
  - **`playbook-*.yaml`** - Main Ansible playbooks for different operating systems
  - **`inventory.yaml`** - Ansible inventory configuration for localhost
  - **`tasks/`** - Ansible task files organized by operating system and functionality
- **`files/`** - Contains all dotfiles and configuration files that get symlinked to home directory
- **`Vagrantfile`** - VM configuration for testing Arch Linux setup
- **`terraform/`** - Manages this repository's `SLACK_WEBHOOK_URL` Actions
  secret. State is in the Cloudflare R2 bucket `dotfiles-terraform-state`;
  `run.sh` reads its key and `main.tfvars` from the gitignored `.secrets` link
  to matrix-secrets, so no AWS credentials or encrypted files are needed. See
  [Terraform](provisioning.md#terraform).

### Configuration Management

The system uses Ansible to create symbolic links from `files/` directory to appropriate locations in the user's home directory. Each playbook imports relevant tasks based on the target operating system.

### Key Task Categories

- **ansible/tasks/files.yaml** - Core dotfile symlinking (shell configs, git, vim, etc.)
- **ansible/tasks/macos/files.yaml** - macOS-specific configurations
- **ansible/tasks/arch-linux/** - Arch Linux specific tasks including package installation and system configuration

### Shell Scripts and Functions

- **`files/shellcheck/`** - Contains shell scripts that are linted via pre-commit hooks
- **`files/functions`** and **`files/functions-zsh`** - Shell utility functions
- Configuration files for various tools: vim, tmux, git, zsh, bash, cursor, etc.

## Pre-commit Configuration

The repository uses pre-commit hooks for quality assurance:

- YAML validation
- Trailing whitespace removal
- End-of-file fixing
- Merge conflict detection
- Shellcheck linting for shell scripts in `files/shellcheck/`
- Ansible-lint for Ansible playbooks and tasks in `ansible/`

## Maintenance scripts

The public `runAnsible.sh` command stays at the repository root. Its internal
preview and apply guard lives in `scripts/deploy/ansible_safe_run.py`, with
regression tests in `tests/`. Keep the guard's audit and state checks intact when
changing paths or callers. Terraform's cohesive native scripts stay in
`terraform/`; deployable shell configuration stays under `files/`.

Future maintenance helpers use purpose-based `scripts/` directories. Keep normal
command entrypoints stable and update tests, CI, documentation, and imports with
any move. Shared branch, review, PR, and managed-skill mechanics come from the exact
agent-tool pin; provisioning algorithms and validation remain repository-owned.

## Shared validation

After documented dependency setup, `bun run check` records the complete local
validation sequence with the pinned agent-tool. CI preserves its platform
integration checks and validates the actual PR or destination branch through
`bun run lint:branch-name <name>`. Feature branches use `<type>/<topic>`;
there is no added branch-length cap. Repository-owned provisioning gates remain
unchanged. The managed `ship-pr` and `reset` skills use shared branch, PR, and
confirmed-merge cleanup commands.
