# Overview

Dotfiles and Ansible tasks for package installaton / system configuration.

Arch Linux system is provisionable via `vagrant up`.

## Developing

Install pre-commit

    pyenv install `cat .python-version`
    pyenv local `cat .python-version`
    pip install -r requirements.txt
    pre-commit install
    pre-commit run --all-files

Install the agent tooling and check the shared agent skills (requires Bun)

    bun install
    bun run agents:check

Agents ship changes with the `ship-pr` skill; see `AGENTS.md`.

## MacOS

Configure via Ansible

    ./runAnsible.sh

Configure via Ansible (dry run)

    ./runAnsible.sh --check

Run specific tags in the playbook

    ./runAnsible.sh --tags 'files'

## Arch Linux

Configure via Ansible

    ./runAnsible.sh

Run specific tags in the playbook

    ./runAnsible.sh --tags 'files'

### Vagrant

Start a Virtualbox VM

    vagrant plugin update
    vagrant box update
    vagrant up
    # login
    vagrant ssh

Start rsyncing Vagrant files

    vagrant rsync-auto

Run provisioners on the running instance

    vagrant provision

Destroy the VM

    vagrant destroy

## Terraform GitHub provider

The GitHub provider now uses `integrations/github` at version 6.13.0.
After decrypting the backend and variables and configuring AWS credentials,
initialize from the `terraform` directory with `./init.sh`. For existing state
that still references `hashicorp/github`, migrate the provider address once:

    terraform state replace-provider registry.terraform.io/hashicorp/github registry.terraform.io/integrations/github

This changes the provider address in state without recreating resources.
Run `terraform plan -var-file=main.tfvars -out=upgrade.tfplan` and inspect the
plan before applying it with `terraform apply upgrade.tfplan`. Do not apply a
plan with deletions or replacements. Keep saved plans outside version control
because they can contain secrets.
