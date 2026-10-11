# Provisioning

Use the commands in the [README](../README.md) for everyday provisioning.
Install the pinned tools and Python dependencies first; use `runAnsible.sh` so
its preview guard runs before Ansible applies changes.

## Ansible preview guard

`runAnsible.sh` audits the selected playbook and its static imports before
running `--check --diff`. It requires complete localhost and loop results,
prints the proposed targets without file contents or preference values,
rejects deletions, file overwrites, changed symlink targets, missing sources,
and unsupported effects, and checks that configuration and file state still
match before applying the same arguments. Existing configuration files are
preserved; reconcile conflicting destinations manually before running it.
macOS restart handlers have an equivalent read-only preview with
`killall -s Finder` / `killall -s SystemUIServer`; macOS `killall(1)` documents
that `-s` sends no signals. The subsequent apply retains the normal handlers.
The wrapper uses the active Python environment, including PyYAML from
`requirements.txt`, and accepts `--check`, `--diff`, `--tags`, `--skip-tags`,
and `-e`/`--extra-vars`. It fixes the repository Ansible configuration and
collection path to that Python's installed packages, removes inherited Ansible
and Python plugin overrides, and rechecks selected macOS preferences before
applying. A user-level configuration or collection cannot shadow the audited
tasks. Implicit `group_vars` and `host_vars` loading is disabled, so adjacent
variable files cannot add templates to the preview. Local plugin and collection
directories are rejected. The supported playbooks disable executable local
facts, Facter, and Ohai during preview and apply. Recursive file operations
are rejected because their descendant changes cannot be proven by this guard.

For isolated functional tests, set an absolute `dotfiles_home` and the Python
interpreter used by the controller:

    ./runAnsible.sh --tags files -e "dotfiles_home=/tmp/dotfiles-test-home ansible_python_interpreter=$(command -v python3)"

Both required CI jobs run the guarded apply against their actual runner and
inventory, with configuration destinations under `RUNNER_TEMP`. The macOS
job also checks its normal user preferences and restart handlers. CI uses
`.python-version` for both controller and target Python and checks the committed
pre-commit revisions without updating them during validation.

## Arch Linux and Vagrant

The guard currently blocks Arch provisioning: pacman, reflector, reboot, and
VM cleanup effects lack a complete non-destructive preview. Do not use a direct
playbook run or Vagrant provisioning as an upgrade-safety bypass. Arch tasks
and package lists remain available, but the existing `Vagrantfile` also runs
destructive keyring and cache operations directly. Review those effects and
establish a complete preview before any future provisioning work.

## Legacy Terraform state

The provider source is declared in [`terraform/main.tf`](../terraform/main.tf).
Existing state may still reference `hashicorp/github` instead of
`integrations/github`. That requires a separately authorized, one-time provider
address migration before using the normal Terraform workflow:

    terraform state replace-provider registry.terraform.io/hashicorp/github registry.terraform.io/integrations/github

Run this only from the `terraform` directory with the intended real backend
initialized. It changes the provider address in state without recreating
resources. Do not mutate state to validate a dependency upgrade; if this migration
is needed, hold that upgrade group. See [Terraform upgrades](dependency-upgrades.md#terraform)
for initialization, saved plans, and apply restrictions.
