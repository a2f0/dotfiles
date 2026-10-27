# Provisioning

Use the commands in the [README](../README.md#provisioning) for everyday provisioning.
Install the pinned tools and Python dependencies first; use `runAnsible.sh` so
its preview guard runs before Ansible applies changes.

## Ansible preview guard

`runAnsible.sh` invokes `scripts/deploy/ansible_safe_run.py` to audit the selected playbook and its static imports before
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

## Terraform

[`terraform/`](../terraform) manages this repository's `SLACK_WEBHOOK_URL`
GitHub Actions secret. Its state is the object `terraform.tfstate` in the
Cloudflare R2 bucket `dotfiles-terraform-state`, read through the S3 backend
with lockfile locking, so Terraform 1.10 or later is required. The backend
settings are committed in [`terraform/main.tf`](../terraform/main.tf); the
bucket and its token were created by hand and are not managed here. No AWS
account is involved.

`.secrets` is a gitignored link to this project's folder in `matrix-secrets`,
which the matrix workspace manages and backs up
([a2f0/matrix `docs/secrets.md`](https://github.com/a2f0/matrix/blob/main/docs/secrets.md)).
Link it from the repository root and confirm Git ignores it:

    ln -s ../matrix-secrets/dotfiles .secrets   # ../../../ from a matrix checkout
    git check-ignore .secrets

`terraform/run.sh` runs a Terraform command from the `terraform` directory. It
loads `.secrets/prod/shared.env` when present and then `.secrets/prod/app.env`,
which wins, and stops before running Terraform when `app.env`,
`TF_STATE_ACCESS_KEY_ID`, or `TF_STATE_SECRET_ACCESS_KEY` is missing. That pair
is the R2 S3 key of a token limited to the state bucket. Only Terraform receives
it, as `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, after `AWS_PROFILE` and
`AWS_SESSION_TOKEN` are unset, so an ambient AWS profile or session cannot
redirect the backend. `init.sh` and `apply.sh` run through it. `init.sh` passes
`-reconfigure`, so a working directory initialized for the former S3 bucket
switches to R2 without offering to migrate state.

`.secrets/prod/main.tfvars` supplies the owner, repository, and webhook URL.
`run.sh` passes it as the first `-var-file` to `plan`, `apply`, `destroy`,
`refresh`, `import`, and `console`, so a later `-var` or `-var-file` wins, and
stops before running Terraform when it is missing. Other subcommands, such as
`init`, `show`, and `state`, run without it. It holds no token: the GitHub
provider takes its token from `TF_VAR_github_access_token`, for example
`gh auth token`, or Terraform prompts for it. From the `terraform` directory:

    ./init.sh
    TF_VAR_github_access_token="$(gh auth token)" ./run.sh plan

See [Terraform upgrades](dependency-upgrades.md#terraform) for saved plans and
apply restrictions.
