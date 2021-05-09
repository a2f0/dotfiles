# Overview

Dotfiles and Ansible tasks for package installaton / system configuration.

Arch Linux system is provisionable via `vagrant up`.

## MacOS

Configure via Ansible

    ansible-playbook -i inventory.yaml playbook-macos.yaml  -l 127.0.0.1

Configure via Ansible (dry run)

    ansible-playbook -i inventory.yaml playbook-macos.yaml --check -l 127.0.0.1

Run specific tags in the playbook

    ansible-playbook -i inventory.yaml playbook-macos.yaml  -l 127.0.0.1 --tags 'files'

## Arch Linux

Configure via Ansible

    ansible-playbook -i inventory.yaml playbook-arch-linux.yaml  -l 127.0.0.1

Run specific tags in the playbook

    ansible-playbook -i inventory.yaml playbook-arch-linux.yaml -l 127.0.0.1 --tags 'files'

## CS

    ansible-playbook -i inventory.yaml playbook-cs.yaml -l linux.cs.uchicago.edu

### Vagrant

Start a Virtualbox VM

    vagrant up

Start rsyncing Vagrant files

   vagrant rsync-auto

## Developing

Install pre-commit to lint files

1. run `pre-commit install` to configure pre-commit hook.
