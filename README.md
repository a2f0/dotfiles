# dotfiles

Shell, Git, editor, terminal, tmux, mail, and chat configuration, plus the
Ansible playbooks that install it. The files live in `files/`; the playbooks in
`ansible/` symlink them into the home directory on macOS and on Ubuntu 24.04 or
Linux Mint 22, and set a few macOS preferences. The Arch Linux playbooks, which
also install packages, are kept but currently blocked. `runAnsible.sh` picks the
playbook for the current host and applies it only after a guarded dry-run finds
no destructive or unsupported changes.

## Quick start

Install [mise](https://mise.jdx.dev/), plus `shellcheck` and `luacheck` for the
pre-commit hooks ([details](docs/development.md#setup-and-installation)).

```sh
mise install                     # pinned Bun, Node, Python, Ansible, pre-commit
python3 -m venv .venv            # with the pinned Python from mise
. .venv/bin/activate
pip install -r requirements.txt
bun install
pre-commit install
./runAnsible.sh --check          # macOS: preview changes without applying them
```

## Provisioning

`runAnsible.sh` runs the playbook for the host after an automatic guarded
dry-run. It rejects destructive or unsupported changes and preserves existing
configuration files, so reconcile conflicting destinations manually before
running it. The [provisioning guide](docs/provisioning.md) describes the guard
and isolated test runs.

### macOS

```sh
./runAnsible.sh                  # preview, then apply
./runAnsible.sh --check          # preview only
./runAnsible.sh --tags 'files'   # run only the tasks with this tag
```

### Ubuntu and Linux Mint

Start from an existing checkout and identify it explicitly; the guard blocks
cloning into an absent checkout. Add `--check` to preview only.

```sh
./runAnsible.sh -e "dotfiles_dir=$(pwd) clone_dotfiles=false ansible_python_interpreter=$(command -v python3)"
```

### Arch Linux

Arch provisioning is blocked because package, reboot, and VM cleanup effects
lack a complete safe preview. Do not bypass the guard with direct playbook or
Vagrant commands. See [provisioning limits](docs/provisioning.md#arch-linux-and-vagrant).

## Development

```sh
bun run check                          # both below, Markdown lint tests, skill check
pre-commit run --all-files             # hooks over every file
python3 -m unittest discover -s tests  # preview guard and Terraform wrapper tests
```

The [development guide](docs/development.md) covers the repository layout,
script locations, individual checks, and hook details.

## Maintenance

[Dependency upgrades](docs/dependency-upgrades.md) covers upgrade procedures,
active compatibility constraints, security exceptions, and Terraform previews.

`terraform/` manages this repository's `SLACK_WEBHOOK_URL` Actions secret. Its
state is in Cloudflare R2, and its scripts read the state key and the Terraform
variables from the gitignored `.secrets` link to matrix-secrets; see
[Terraform](docs/provisioning.md#terraform).
