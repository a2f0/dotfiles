# ANTIGRAVITY.md

This file provides guidance to Antigravity when working with code in this repository.

## Repository Overview

This is a dotfiles repository that manages system configuration and package installation across multiple operating systems (primarily macOS and Arch Linux) using Ansible playbooks.

## Development Commands

### Setup and Installation

```bash
# Install Python dependencies and set up pre-commit hooks
pyenv install $(cat .python-version)
pyenv local $(cat .python-version)
pip install -r requirements.txt
pre-commit install
```

### Linting

```bash
pre-commit run --all-files
```

## Code Style

- **Ansible**: Use loops for repetitive tasks. Keep tasks idempotent.
- **Shell**: Use `shellcheck` compliant code.
- **Commit Messages**: Follow Conventional Commits.

## Workflows

- Use `.agent/workflows/` for common tasks.
