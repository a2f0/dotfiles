# Provisioning

Use the commands in the [README](../README.md#provisioning) for everyday provisioning.
Install the pinned tools first; `runAnsible.sh` creates the checkout's `.venv`
with `python3` if absent and installs `requirements.txt`, including its constraints,
on each invocation. Satisfied packages are reused. This also happens for `--check`
and `--help`; only the environment is bootstrapped, not system configuration.
Missing pip is bootstrapped with `ensurepip`, including in a partially created
environment. Dependency installation must succeed before the preview guard or
Ansible runs.
The launcher works from outside the checkout and does not require activation or
install into the ambient Python environment. Python must provide `venv` and pip;
on Ubuntu, install `python3-venv` if the system Python lacks them.

The launcher defaults `dotfiles_dir` to its own checkout, `clone_dotfiles` to
`false`, and `ansible_python_interpreter` to its `.venv/bin/python3`. These values
are shared by the audit, preview, and apply, so Ubuntu and Linux Mint need no
extra variables for a normal first run. Explicit `-e` overrides still pass through
the guard; enabling cloning or selecting another Python remains blocked.

The bootstrap reuses an existing `.venv`; it does not upgrade its Python or delete
it. Start with the pinned Python on PATH and follow the
[Python upgrade procedure](dependency-upgrades.md#scope-and-compatibility) when
changing that interpreter. Installing missing packages may access the configured
package index and execute package build code, even with `--check` or `--help`.

## Git and GitHub

Git reaches GitHub only over SSH. `files/gitconfig` rewrites
`https://github.com/` URLs to SSH and runs SSH with `files/git-ssh_config`,
which connects to `ssh.github.com` on port 443, so a blocked port 22 needs no
HTTPS fallback; `files/github_known_hosts` pins GitHub's published host keys.
It also clears the macOS keychain credential helper for `https://github.com`,
so nothing waits on a keychain prompt. Have `gh` use SSH too; a per-host
setting overrides the global one, so set both:

    gh config set git_protocol ssh
    gh config set git_protocol ssh --host github.com

## OfflineIMAP

On macOS, install the mail client and its TLS transport with
`brew install offlineimap openssl@3`. On Linux, the transport uses
the system OpenSSL CLI and its CA trust store. With the Gmail app password
in `GMAIL_APP_SPECIFIC_PASSWORD`, run `offlineimap --info` to verify login
and list folders before the first sync.

## SSH terminal titles

SSH Zsh sessions show `hostname: /full/current/path` in Ghostty's title at each
prompt; local titles are unchanged. Install the dotfiles on the remote host and
open a new SSH shell to activate this native Zsh hook. No plugins or Oh My Zsh
are needed.

## OMP configuration

`files/omp/config.yml` manages the default profile's
`~/.omp/agent/config.yml`. `files/omp/extensions/hostname.ts` supplies the short
hostname (before the first dot) in OMP's status line, alongside the model,
directory, Git branch, and PR. `statusLine.compactThinkingLevel: false` names
the model's thinking level (effort) beside it, such as `◕ xhigh`, instead of
showing only an icon. Other extension statuses share the hostname's inline
segment; the duplicate footer status row is disabled.

Install OMP separately. On a new machine, provision its configuration before
the first launch, then complete setup and authenticate locally:

    ./runAnsible.sh --tags omp

The normal `files` tag includes these tasks on macOS, Ubuntu/Linux Mint, and
files-only Arch. Only the config file and hostname extension are linked;
credentials, databases, sessions, logs, caches, other extensions, and named
profiles remain local.

Before the first apply, review any existing `~/.omp/agent/config.yml` and merge
desired non-secret preferences into `files/omp/config.yml`. Move the existing
file to a private backup outside the checkout; the guard deliberately refuses
to overwrite it. Reconcile an existing `extensions/hostname.ts` the same way.
Until conflicts are reconciled, use `./runAnsible.sh --skip-tags omp` to
provision the other dotfiles. Restart OMP after installing the extension.

OMP preserves the config symlink when `/settings`, `/model`, or `omp config set`
saves global preferences, so intentional preference changes update the tracked
file. Diagnostic consent is intentionally shared at the owner's request:
`dev.autoqaConsent: granted`. Review saved changes before committing; keep
credentials in OMP's local credential store or local environment, never in the
tracked config.

Keep OMP's native YAML format: block-style lists and no final newline. The
end-of-file hook exempts only this file so hooks and OMP do not repeatedly
rewrite it. Other YAML and whitespace checks still apply.

OMP creates `config.yml.lock` beside the resolved symlink target. Git ignores
that runtime lock; it is not configuration and must not be committed or deleted
while OMP may be using it. Ordinary saves that preserve the preferences should
leave the checkout clean. Actual preference changes and new first-run onboarding
state (`setupVersion`) remain visible in Git and require review before committing.

## Codex configuration

`files/codex/dotfiles.config.toml` manages the named profile
`~/.codex/dotfiles.config.toml`, not the writable main config. Install Codex
0.169.0 or newer separately, provision the profile, and select it explicitly:

    ./runAnsible.sh --tags codex
    codex --profile dotfiles

The normal `files` tag includes this profile on macOS, Ubuntu/Linux Mint, and
files-only Arch. Codex's native status line shows the model/reasoning, hostname,
directory, Git branch, remaining context, and the percentage of the weekly cap
left when Codex reports a limit. In Codex 0.170.0, press `s` at the final
`/model` picker choice to use it only for the current session.

The profile shares model, reasoning, approval-reviewer, and shell-environment
preferences. Codex's
[named profiles](https://developers.openai.com/codex/config-advanced/)
overlay `~/.codex/config.toml`; CLI overrides and trusted project configuration
take precedence over the profile. Plain `codex` still uses the local main config.
There is no default-profile setting, and not all subcommands accept `--profile`,
so the dotfiles do not alias the `codex` command.

Keep project trust records and other local settings in `~/.codex/config.toml`.
All MCP server definitions and tool approval policies stay there too, including
machine-specific command paths; this profile does not define MCP servers.
Authentication, sessions, history, databases, caches, and logs
are not linked or imported. Never point `CODEX_HOME` into the checkout or put
credentials in the profile.

Codex saves `/statusline` changes to the selected profile while preserving its
symlink. Keep the native `status_line_use_colors` setting so an unchanged save
does not add it later. Startup and unchanged status-line saves should leave the
profile unchanged; intentional preference changes remain visible for review.

An existing `~/.codex/dotfiles.config.toml` blocks installation rather than being
overwritten. Review and merge its desired non-secret preferences, then move it
to a private backup outside the checkout before applying. The existing main
config needs no migration. Use `./runAnsible.sh --skip-tags codex` to provision
other dotfiles without installing this profile.

## Claude Code configuration

`files/claude/settings.json` manages the user settings file
`~/.claude/settings.json`. Its status line runs `files/claude/statusline.py`,
linked as `~/.claude/statusline.py`, which shows the working folder the way
OMP's `path` segment does: a linked Git worktree shows `🌳 project`, adding
`/directory` when the directory is not named after the branch; temporary
directories show `🗑` and their path inside the temporary root; the
`~/Projects/`, `~/repos/`, and `/work/` prefixes are dropped; the home directory
becomes `~`; and paths over 40 characters keep their end. The folder is a
`file://` link where the terminal supports links. The next segment names the
Claude identity: a set, non-empty `CLAUDE_CONFIG_DIR` with the home directory
as `~`, then the signed-in email from that directory’s `.claude.json`, such as
`⚙ ~/.claude2 · you@example.com`, or `⚙ you@example.com` for the default
directory. Each part over 40 characters keeps its end. The email appears only
when its account matches the session account ID described below, so another
session’s `/login` in the same directory cannot mislabel this one; a new
session may show it only after its first exchange. Without either part, no
segment appears. Claude Code keeps its own footer badges below this row, and
leaves the row blank in folders you have not trusted. The script needs Python
3.9 or newer as `python3`, and `git`.

Once the session reports subscription limits, `7d All` shows its live weekly
percentage used. `Account 7d` shows Fable usage from the signed-in account’s
`/usage` snapshot in `~/.claude.json` (under `CLAUDE_CONFIG_DIR` when set).
It also shows cached all-model usage if only the live five-hour window is
available. Each cached figure shows its age and disappears when its window
resets. Open `/usage` to refresh the snapshot. Cached figures require a matching session account ID from Claude Code’s
environment or a recent session-owner record in its transcript.

Install Claude Code separately, then provision its configuration:

    ./runAnsible.sh --tags claude

The normal `files` tag includes these tasks on macOS, Ubuntu/Linux Mint, and
files-only Arch. Only the settings file and status-line script are linked;
credentials, `~/.claude.json` (account, MCP servers, and folder trust),
`settings.local.json`, sessions, history, plugins, and caches remain local.

The same tasks prepare `~/.claude2`, a second configuration directory for
another account. The `claude2` shell function runs `claude` with
`CLAUDE_CONFIG_DIR=~/.claude2`, so that install keeps its own login,
`.claude.json`, sessions, history, plugins, and the skills its account syncs
into `skills/synced`; run `/login` in it once. Its `settings.json` links to the
same tracked file, so preferences saved from either install apply to both, and
its status line runs the script in `~/.claude`, which shows `⚙ ~/.claude2` with
the second account’s email and reads its `/usage` snapshot. Plain `claude`
still uses `~/.claude`.

Shared user-wide skills reach both directories through
`agent-tool skills link --apply`, which the matrix workspace’s `bun run sync`
and the setup of each repository declaring such skills in its `agent-tool.json`
run. It links them into `skills/` in `CLAUDE_CONFIG_DIR`, `~/.claude`, and each
other `~/.claude*` directory holding `settings.json` or `.claude.json`, so
rerun either after first provisioning `~/.claude2`. User-scope MCP servers live
in each directory’s `.claude.json`, so register each one again for the second
account with `claude2 mcp add --scope user <name> -- <command>`.

Before the first apply, review any existing `~/.claude/settings.json` and merge
desired non-secret preferences into `files/claude/settings.json`. Move the
existing file to a private backup outside the checkout; the guard deliberately
refuses to overwrite it. Reconcile an existing `~/.claude/statusline.py` or
`~/.claude2/settings.json` the same way. Until conflicts are reconciled, use
`./runAnsible.sh --skip-tags claude` to provision the other dotfiles.

In Claude Code’s `/model` picker, press `s` on the highlighted model to use it
for this session. Enter saves the default for future sessions.

Claude Code saves user settings from `/model`, `/effort`, `/config`,
`/statusline`, and plugin commands through the symlink into the tracked file,
staging each save beside it as `settings.json.tmp.*`, which Git ignores. Keep
`~/.claude/settings.json` and `~/.claude2/settings.json` direct links into the
checkout: Claude Code resolves only one link, so a link to another link is
replaced by a regular file or fails to save
([anthropics/claude-code#78162](https://github.com/anthropics/claude-code/issues/78162)).
Review saved changes before committing; keep credentials, API keys, and
machine-specific paths out of the tracked file.

The owner has opted to share the dangerous-mode prompt acknowledgement across
these personal machines. Entering bypass mode still requires a separate choice. Review other prompt acknowledgements that Claude Code
saves here before sharing them.

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
The wrapper uses the checkout's `.venv`, including PyYAML from
`requirements.txt`, and accepts `--check`, `--diff`, `--tags`, `--skip-tags`,
and `-e`/`--extra-vars`. It fixes the repository Ansible configuration and
collection path to that Python's installed packages, removes inherited Ansible
and Python plugin overrides, and rechecks selected macOS preferences and
Linux Mint dconf keys with `dconf read` before applying. Only integer dconf
keys conditioned on the Linux Mint fact are audited; the CI Ubuntu job proves
their conditional skip, not the write. A user-level configuration or collection cannot shadow the audited
tasks. Implicit `group_vars` and `host_vars` loading is disabled, so adjacent
variable files cannot add templates to the preview. Local plugin and collection
directories are rejected. The supported playbooks collect only distribution and
user facts, which supply the OS guards, home paths, and file owners. Both the
normal and minimum fact sets are disabled before selecting those collectors;
unrelated host discovery and executable local facts, Facter, and Ohai do not run
during preview or apply. Recursive file operations
are rejected because their descendant changes cannot be proven by this guard.

For isolated functional tests, set an absolute `dotfiles_home`. The launcher uses
its `.venv` interpreter for both controller and target automatically:

    ./runAnsible.sh --tags files -e "dotfiles_home=/tmp/dotfiles-test-home"

Both required CI jobs run the guarded apply against their actual runner and
inventory, with configuration destinations under `RUNNER_TEMP`. The macOS
job also checks its normal user preferences and restart handlers. CI uses
`.python-version` for both controller and target Python and checks the committed
pre-commit revisions without updating them during validation.

## Arch Linux and Vagrant

The default Arch playbook only creates configuration directories and links. It
uses the same audited preview and non-overwrite checks as macOS and Ubuntu, and
honors `dotfiles_home` for isolated testing. It does not install packages, change
users, rewrite mirrors, or reboot.

The old system setup is retained in `ansible/playbook-arch-linux-system.yaml`;
`ansible/playbook-arch-linux-vm.yaml` and `Vagrantfile` also remain legacy,
unsupported paths. The guard has no complete preview for their pacman, reflector,
user-management, and VM cleanup effects. Vagrant additionally deletes and
rebuilds the keyring, clears package caches, and syncs the checkout into the
guest. Its legacy VM playbook also copies the host's SSH keys. Do not bypass
the guard with direct playbook runs or Vagrant provisioning.

For an Arch guest on macOS, use the [QEMU test VM guide](arch-vm.md). It uses
Arch's official x86_64 cloud image and software emulation on Apple Silicon,
without depending on old Vagrant boxes. Booting the guest is separate from
running its guarded dotfiles setup.

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
