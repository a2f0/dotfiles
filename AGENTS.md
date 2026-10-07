# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

Claude Code loads it directly when the repository has no `CLAUDE.md`; its
`instructionFiles` setting defaults to `claude-md-or-agents-md`. Do not add a
`CLAUDE.md`.

## Repository Overview

This is a dotfiles repository that manages system configuration and package installation across multiple operating systems (primarily macOS and Arch Linux) using Ansible playbooks. The repository contains configuration files for various development tools and system utilities, along with automation scripts for provisioning environments.

## Development Commands

### Setup and Installation

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

### Linting and Quality Checks

```bash
# Run all pre-commit hooks on all files
pre-commit run --all-files

# Run specific pre-commit hook
pre-commit run shellcheck
pre-commit run luacheck
pre-commit run check-yaml

# Check that the shared agent skills are current
bun run agents:check

# Verify the Ansible preview safety gate
python3 -m unittest discover -s tests
bun run test:markdownlint
```

### System Provisioning

#### macOS

```bash
# Configure macOS system via Ansible
./runAnsible.sh

# Dry run to see what would change
./runAnsible.sh --check

# Run only specific tasks (e.g., file symlinks)
./runAnsible.sh --tags 'files'
```

#### Arch Linux

Arch provisioning is currently blocked by the preview guard because package,
reflector, reboot, and VM cleanup effects lack a complete safe preview. Do not
invoke playbooks or Vagrant directly to bypass it during dependency upgrades.
See README for the separately reviewed provisioning workflow.

#### Vagrant Development Environment

```bash
# Start and provision VM
vagrant plugin update
vagrant box update
vagrant up
vagrant ssh

# Auto-sync files during development
vagrant rsync-auto

# Re-run provisioners on running instance
vagrant provision

# Clean up
vagrant destroy
```

## Architecture

### Core Structure

- **`ansible/`** - Contains all Ansible playbooks, inventory, and tasks
  - **`playbook-*.yaml`** - Main Ansible playbooks for different operating systems
  - **`inventory.yaml`** - Ansible inventory configuration for localhost
  - **`tasks/`** - Ansible task files organized by operating system and functionality
- **`files/`** - Contains all dotfiles and configuration files that get symlinked to home directory
- **`Vagrantfile`** - VM configuration for testing Arch Linux setup

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

## Conventions

- Work on a feature branch named `<type>/<topic>`. Commits and PR titles use
  Conventional Commits with an imperative subject of at most 50 characters.
  Wrap commit bodies at 72 characters.
- Commits are signed; never skip signing with `--no-gpg-sign`. Do not add
  `Co-authored-by` trailers or attribution footers, and do not force-push.

## Shipping

Use the `ship-pr` skill with `agent-tool` (`bun run agent-tool ...`). Review
with an agent other than the one that wrote the change. Title and required
check policy is in `agent-tool.json`; packages are not versioned.

The `Github Actions` workflow runs on every push. Its `code-quality` job checks
the agent skills, runs pre-commit and guard regressions, and applies the macOS
playbook; its `ansible-ubuntu` job applies the Ubuntu playbook. Both first audit
the tasks and require a complete safe `--check --diff` preview against the same
runner, inventory, variables, interpreter, and selected tasks. CI isolates file
destinations with `dotfiles_home` under `RUNNER_TEMP`; macOS preferences and
restart handlers retain their functional validation. Never replace these applies
with check-only tests. Both must pass. Branch
protection on `main` also requires resolved review conversations. If a run is
cancelled, rerun it with `gh run rerun <run-id>` rather than pushing an empty
commit. Merging deploys nothing; run `./runAnsible.sh` on a machine to apply
changes.

Gemini Code Assist (configured in `.gemini/config.yaml`) is a GitHub App that
reviews pull requests automatically when enabled; do not request it with
`gh pr edit --add-reviewer`. When handling review feedback, reply in its
original review thread, not the PR conversation, through
`POST /repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies`,
name the commit that addresses it, and resolve only fully addressed findings.

After upgrading `@a2f0/agent-tool`, run `bun run agents:sync` and commit the
skills with `.agent-tool-skills.json`. Do not edit the managed skills in
`.agents/skills` or `.claude/skills`.

Use the managed `update-dependencies` skill for dependency upgrades. Keep all
runtime pins synchronized and check controller and target Python against the
Ansible support matrix. Always dry-run before infrastructure mutation, including
CI triggered by a push, and skip compatibility groups with destructive,
unsupported, or incomplete previews. Do not change Terraform state or run Arch
cleanup/reboots to validate an upgrade. See README for the preview limits.
