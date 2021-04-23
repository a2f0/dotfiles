# Overview

System bootstrapper for MacOS and Arch Linux.

## MacOS

Configure via Ansible

    ansible-playbook -i inventory.yaml playbook-macos.yaml  -l 127.0.0.1

Configure via Ansible (dry run)

    ansible-playbook -i inventory.yaml playbook-macos.yaml --check -l 127.0.0.1

## Installation

Build the system

    ./build_me.sh
