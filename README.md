# Overview

Dotfiles and Ansible tasks for package installaton / system configuration.

Arch Linux system is provisionable via `vagrant up`.

## Developing

Install pre-commit

    pre-commit install

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
