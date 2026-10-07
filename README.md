# Overview

Dotfiles and Ansible tasks for package installation / system configuration.

The legacy `Vagrantfile` provisions Arch Linux with package and keyring changes
that have no complete non-destructive preview. It is not part of the dependency
upgrade path described below.

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

The markdownlint pre-commit hook uses the Bun-locked local CLI with the same
Markdown file scope and `.markdownlint.yaml` rules. Install Bun dependencies
before running hooks; use the Node version pinned in `.nvmrc` / `.mise.toml`.
CI selects that exact Node version before running the hook.

## MacOS

Configure via Ansible, after an automatic guarded dry-run

    ./runAnsible.sh

Configure via Ansible (dry run)

    ./runAnsible.sh --check

`runAnsible.sh` audits the selected playbook and its static imports before
running `--check --diff`. It requires complete localhost and loop results,
prints the proposed targets without file contents or preference values,
rejects deletions, file overwrites, changed symlink targets, missing sources,
and unsupported effects, and checks that configuration and file state still
match before applying the same arguments. Existing configuration files are
preserved; reconcile conflicting destinations manually before running it.
macOS restart handlers have an equivalent read-only preview with
`killall -s Finder` / `killall -s SystemUIServer`; macOS `killall(1)` documents
that `-s` sends no signals. The subsequent apply retains the normal handlers.
The wrapper uses the active Python environment, including PyYAML from
`requirements.txt`, and accepts `--check`, `--diff`, `--tags`, `--skip-tags`,
and `-e`/`--extra-vars`. It fixes the repository Ansible configuration and
collection path to that Python's installed packages, removes inherited Ansible
and Python plugin overrides, and rechecks selected macOS preferences before
applying. A user-level configuration or collection cannot shadow the audited
tasks. The supported playbooks gather system facts with local executable facts
disabled, so an `/etc/ansible/facts.d` script cannot run during the preview.

For isolated functional tests, set an absolute `dotfiles_home` and the Python
interpreter used by the controller:

    ./runAnsible.sh --tags files -e "dotfiles_home=/tmp/dotfiles-test-home ansible_python_interpreter=$(command -v python3)"

Both required CI jobs run the guarded apply against their actual runner and
inventory, with configuration destinations under `RUNNER_TEMP`. The macOS
job also checks its normal user preferences and restart handlers. CI uses
`.python-version` for both controller and target Python and checks the committed
pre-commit revisions without updating them during validation.

Run specific tags in the playbook

    ./runAnsible.sh --tags 'files'

## Ubuntu and Linux Mint

The clone task cannot be proved safe when the source checkout is absent, so the
guard stops before applying. Start from an existing checkout and identify it
explicitly, as CI does:

    ./runAnsible.sh -e "dotfiles_dir=$(pwd) clone_dotfiles=false ansible_python_interpreter=$(command -v python3)"

## Arch Linux

The guard currently blocks Arch provisioning: pacman, reflector, reboot, and
VM cleanup effects lack a complete non-destructive preview. Do not use a direct
playbook run or Vagrant provisioning as an upgrade-safety bypass. Arch tasks
and package lists remain available, but the existing `Vagrantfile` also runs
destructive keyring and cache operations directly. Review those effects and
establish a complete preview before any future provisioning work.

## Terraform GitHub provider

Terraform uses `integrations/github` at version 6.13.0.
After decrypting the backend and variables and configuring AWS credentials,
initialize from the `terraform` directory with `./init.sh`. For existing state
that still references `hashicorp/github`, migrate the provider address once:

    terraform state replace-provider registry.terraform.io/hashicorp/github registry.terraform.io/integrations/github

This changes the provider address in state without recreating resources.
Run `terraform plan -var-file=main.tfvars -out=upgrade.tfplan` and inspect the
plan with `terraform show -json upgrade.tfplan > upgrade.tfplan.json` and
`bun run agent-tool dependencies check-terraform-plan upgrade.tfplan.json`
before an authorized apply with `terraform apply upgrade.tfplan`. Use the real
backend and variables; do not use `apply.sh` during dependency upgrades because
it generates a fresh, uninspected plan. Do not apply a
plan with deletions or replacements. Saved `*.tfplan` files are ignored by Git because they can contain secrets.
Delete saved plans after applying them.

## Dependency upgrades

Use the managed `update-dependencies` skill and inventory manifests, locks,
all mise tools, Python controller/target support, Ansible collections, action
refs, Terraform, OS packages, and tool bootstrap scripts. Ansible 14.5.0 uses
core 2.21.5: its supported controller Python is 3.12–3.14 and target Python is
3.9–3.14. Read the upstream porting guide before changing that combination.
Skip infrastructure groups without a complete real-environment preview;
encrypted Terraform credentials/state and unavailable Arch hosts are concrete
validation limits, not evidence of a safe upgrade.

The `smol-toml` 1.9.0 security override fixes
[GHSA-r4xh-jqrq-34v2](https://github.com/squirrelchat/smol-toml/security/advisories/GHSA-r4xh-jqrq-34v2)
while markdownlint-cli2 0.23.3 pins 1.8.0. This repository's only consumer is
the local markdownlint CLI. Its parser uses the named `parse` export, and its
configuration merge copies properties with object spread, which accepts the
new null-prototype results. Markdownlint's rule normalization additionally checks
`instanceof Object`, so Bun's version-bound `markdownlint@0.41.1` patch accepts
null-prototype objects without changing how previously accepted values behave.
Without the patch, nested TOML rule options silently lose their settings.
Regressions exercise actual CLI TOML config pointers, nested rule options and
explicit disabled rules, ignores, invalid input, many flat keys, and existing
YAML rules. The override targets markdownlint-cli2 0.23.3, and a lock-graph regression
requires its reviewed exact version and parser ownership. Remove the override
and patch when the CLI naturally resolves
a fixed parser and markdownlint supports its objects, then require the same
integration tests and fresh audit.

The audit still reports
[braces 3.0.3](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), for which no
patched version was published, and
[KaTeX 0.16.47](https://github.com/advisories/GHSA-238p-pmpm-9mq7), constrained by
markdownlint's math extension to `^0.16.0`. Both remain upstream constraints;
repository-controlled lint patterns and Markdown are their inputs. Do not infer
that a successful lint run resolves these advisories or force an unsupported
replacement to silence the audit.
