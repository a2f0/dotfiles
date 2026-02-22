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
