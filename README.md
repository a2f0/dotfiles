# Overview

## MacOS

Configure via Ansible

    ansible-playbook -i inventory.yaml playbook-macos.yaml  -l 127.0.0.1

Configure via Ansible (dry run)

    ansible-playbook -i inventory.yaml playbook-macos.yaml --check -l 127.0.0.1

Run specific tags in the playbook

    ansible-playbook -i inventory.yaml playbook-macos.yaml  -l 127.0.0.1 --tags 'files'

## Developing

Install pre-commit to lint files

1. run `pre-commit install` to configure pre-commit hook.
