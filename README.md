# dotfiles

Shell, Git, editor, terminal, tmux, mail, and chat configuration, installed with
Ansible. The configuration lives in `files/`; playbooks in `ansible/` link it into
your home directory on macOS, Ubuntu 24.04, and Linux Mint 22. On macOS and
Linux Mint, the playbooks also set desktop preferences.

## Quick start

Install [mise](https://mise.jdx.dev/), then run this from your checkout to install
the pinned tools:

```sh
mise install
```

## Provisioning

Preview the changes before applying them:

```sh
./runAnsible.sh --check          # preview only
./runAnsible.sh                  # preview, then apply
./runAnsible.sh --tags 'files'   # configuration files and directories only
```

The launcher selects the host's playbook and installs its Python dependencies in
`.venv`; you do not need to activate it. Every apply includes a dry-run that
rejects destructive or unsupported changes. Existing configuration files are
preserved, so resolve any reported conflicts before trying again.

Arch Linux provisioning is currently blocked because its package, reboot, and
cleanup tasks cannot be safely previewed. Do not run its playbooks or Vagrant
provisioning directly.

## Documentation

- [Provisioning](docs/provisioning.md): setup details, Git and SSH configuration,
  preview limits, and Terraform.
- [Development](docs/development.md): contributor setup, checks, and repository layout.
- [Dependency upgrades](docs/dependency-upgrades.md): upgrade procedures and
  compatibility constraints.
