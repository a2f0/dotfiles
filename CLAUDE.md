# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a dotfiles repository that manages system configuration and package installation across multiple operating systems (primarily macOS and Arch Linux) using Ansible playbooks. The repository contains configuration files for various development tools and system utilities, along with automation scripts for provisioning environments.

## Development Commands

### Setup and Installation
```bash
# Install Python dependencies and set up pre-commit hooks
pyenv install $(cat .python-version)
pyenv local $(cat .python-version)
pip install -r requirements.txt
pre-commit install
```

### Linting and Quality Checks
```bash
# Run all pre-commit hooks on all files
pre-commit run --all-files

# Run specific pre-commit hook
pre-commit run shellcheck
pre-commit run check-yaml
```

### System Provisioning

#### macOS
```bash
# Configure macOS system via Ansible
ansible-playbook -i inventory.yaml playbook-macos.yaml -l 127.0.0.1

# Dry run to see what would change
ansible-playbook -i inventory.yaml playbook-macos.yaml --check -l 127.0.0.1

# Run only specific tasks (e.g., file symlinks)
ansible-playbook -i inventory.yaml playbook-macos.yaml -l 127.0.0.1 --tags 'files'
```

#### Arch Linux
```bash
# Configure Arch Linux system via Ansible
ansible-playbook -i inventory.yaml playbook-arch-linux.yaml -l 127.0.0.1

# Run only specific tasks
ansible-playbook -i inventory.yaml playbook-arch-linux.yaml -l 127.0.0.1 --tags 'files'
```

#### Vagrant Development Environment
```bash
# Start and provision VM
vagrant plugin update
vagrant box update
vagrant up
vagrant ssh

# Auto-sync files during development
vagrant rsync-auto

# Re-run provisioners on running instance
vagrant provision

# Clean up
vagrant destroy
```

## Architecture

### Core Structure
- **`files/`** - Contains all dotfiles and configuration files that get symlinked to home directory
- **`tasks/`** - Ansible task files organized by operating system and functionality
- **`playbook-*.yaml`** - Main Ansible playbooks for different operating systems
- **`inventory.yaml`** - Ansible inventory configuration for localhost
- **`Vagrantfile`** - VM configuration for testing Arch Linux setup

### Configuration Management
The system uses Ansible to create symbolic links from `files/` directory to appropriate locations in the user's home directory. Each playbook imports relevant tasks based on the target operating system.

### Key Task Categories
- **files.yaml** - Core dotfile symlinking (shell configs, git, vim, etc.)
- **macos/files.yaml** - macOS-specific configurations
- **arch-linux/** - Arch Linux specific tasks including package installation and system configuration

### Shell Scripts and Functions
- **`files/shellcheck/`** - Contains shell scripts that are linted via pre-commit hooks
- **`files/functions`** and **`files/functions-zsh`** - Shell utility functions
- Configuration files for various tools: vim, tmux, git, zsh, bash, cursor, etc.

## Pre-commit Configuration
The repository uses pre-commit hooks for quality assurance:
- YAML validation
- Trailing whitespace removal
- End-of-file fixing
- Merge conflict detection
- Shellcheck linting for shell scripts in `files/shellcheck/`
