# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

Claude Code loads it directly when the repository has no `CLAUDE.md`; its
`instructionFiles` setting defaults to `claude-md-or-agents-md`. Do not add a
`CLAUDE.md`.

## Repository Overview

This is a dotfiles repository that manages system configuration and package installation across multiple operating systems (primarily macOS and Arch Linux) using Ansible playbooks. The repository contains configuration files for various development tools and system utilities, along with automation scripts for provisioning environments.

## Setup and validation

Follow [development](docs/development.md) for pinned tool setup, Python virtual
environment dependencies, hook installation, and repository structure. In agent
shells, put the pinned tools from `~/.local/share/mise/installs` and the configured
`.venv/bin` first on PATH; do not run `mise trust`.

Run `pre-commit run --all-files`, `python3 -m unittest discover -s tests`,
`bun run test:markdownlint`, and `bun run agents:check`. Install dependencies and
pre-commit hooks before committing. Capture noisy finite commands with the pinned
`bun run agent:run --label <check> -- <command>` harness, inspect required warnings,
timings, and artifacts, and keep review verdicts and decision output visible.
The [development guide](docs/development.md#validation) has invocation examples.

Provision only through `runAnsible.sh` and the [provisioning guide](docs/provisioning.md).
Arch and Vagrant effects lack a complete safe preview and remain blocked; do not
bypass the guard with direct playbook or Vagrant commands. Preserve host state and
never provision a real system merely to validate maintenance changes.

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

When handling review feedback, reply in its original review thread, not the
PR conversation, through
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
cleanup/reboots to validate an upgrade. Read
[dependency upgrades](docs/dependency-upgrades.md) for procedures and active
constraints, and [provisioning](docs/provisioning.md) for preview limits.

Keep the root README focused on purpose, setup, and essential safe usage. Put
reusable upgrade procedures and active constraints, override rationale, and removal
conditions in `docs/dependency-upgrades.md`, linking to focused operational docs
where needed. Record each upgrade's version inventory, audit/test/preview results,
and skipped groups in its PR, not README or an accumulating documentation journal.
Keep historical findings attributed to their PR; recheck them before claiming
current status. Update or remove maintenance guidance as constraints change.
