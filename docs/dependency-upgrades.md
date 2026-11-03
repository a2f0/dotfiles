# Dependency upgrades

Use the managed `update-dependencies` skill and the repository's
[development and shipping guidance](../AGENTS.md). This document holds reusable
procedures and active constraints. Put each upgrade's version inventory, migration
results, test/audit/preview evidence, and skipped groups in its PR. Update these
instructions when a constraint changes or is removed; do not append run journals.

## Scope and compatibility

Inventory manifests, locks, all mise tools, Python controller/target support,
Ansible collections, action refs, Terraform, OS packages, and bootstrap scripts.
Read pins from [`.mise.toml`](../.mise.toml), [`.python-version`](../.python-version),
[`.nvmrc`](../.nvmrc), [`requirements.txt`](../requirements.txt), and the owning
manifests and locks. Keep duplicated runtime pins synchronized. Check the
controller and target Python versions against the selected Ansible release's
support matrix and read its upstream porting guide before changing the group.

Keep Python on 3.14 while Ansible 14 uses core 2.21: the community
package requires `ansible-core~=2.21.5`, and its
[support matrix](https://docs.ansible.com/projects/ansible-core/devel/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix)
supports controller Python 3.12–3.14 and target Python 3.9–3.14. Do not
independently install core 2.22 or community.general 14 over this collection
bundle. Move those majors together with a compatible Ansible community release,
read its porting guide, and repeat the complete guarded previews and
controller/target checks below. There are no separately installed roles.

Verify the executable's `python3 --version`, not only `.venv/pyvenv.cfg`, after
changing Python. An in-place `venv --upgrade` can retain an old launcher. If
that happens, preserve the old environment outside the checkout, create a fresh
`.venv` with the exact selected interpreter, reinstall requirements and hooks,
and verify both controller and target interpreters before previewing.

## Python tooling security floors

[`requirements-constraints.txt`](../requirements-constraints.txt) sets security
floors for filelock and virtualenv without adding them as top-level tools. The
existing ansible-lint and pre-commit ranges allow these versions, but an existing
virtual environment otherwise satisfies those ranges with vulnerable releases.
The constraints are consumed by the normal requirements install in development
and both CI jobs.

filelock's [security advisories](https://github.com/tox-dev/filelock/security/advisories)
cover local lock-file races; virtualenv's
[security advisories](https://github.com/pypa/virtualenv/security/advisories)
cover generated activation scripts and environment creation. Use private caches
and trusted environment paths; recreate affected generated environments rather
than assuming a package upgrade rewrites them. Revisit the floors when the owning
tools require fixed versions themselves. Verify removal with a fresh resolved
Python advisory audit, `pip check`, pre-commit, and the full validation group.

## Infrastructure boundaries

Skip infrastructure groups without a complete real-environment preview.
Missing Terraform credentials or variables and unavailable Arch hosts are
validation limits, not evidence of a safe upgrade. Do not change Terraform state
or run Arch cleanup/reboots to validate an upgrade. The
[provisioning guide](provisioning.md) describes the Ansible guard, CI applies,
blocked Arch/Vagrant effects, and the Terraform state backend.

## Terraform

Inspect initialization and planning effects before execution. With `.secrets`
linked and the GitHub token set as described in
[provisioning](provisioning.md#terraform), initialize from the `terraform`
directory with `./init.sh` against the real R2 backend. Hold the group if
initialization needs a backend or state migration.

Create and inspect a saved plan from that same directory. `run.sh` supplies the
state credentials to each Terraform command and `.secrets/prod/main.tfvars` to
`plan` and `apply`:

    ./run.sh plan -input=false -out=upgrade.tfplan
    ./run.sh show -json upgrade.tfplan > upgrade.tfplan.json
    bun run --cwd .. agent-tool dependencies check-terraform-plan terraform/upgrade.tfplan.json

Inspect resource identities, drift, warnings, and effects outside resource actions
as well as the helper's result. Do not apply a plan with deletions or replacements,
or one whose safety cannot be established. Before an authorized apply, verify
that the validated configuration, toolchain, environment, and state still match
that preview, then consume the saved plan with `./run.sh apply upgrade.tfplan`;
Terraform refuses it if `main.tfvars` no longer matches the plan. Do not use
`apply.sh` during dependency upgrades because it generates a fresh, uninspected
plan. Saved binary and JSON plans are ignored by Git because they can contain
secrets; keep them private and delete them after use.

## Markdownlint parser compatibility

The local markdownlint-cli2 0.24.0 naturally resolves `smol-toml` 1.9.1,
which addresses
[GHSA-r4xh-jqrq-34v2](https://github.com/squirrelchat/smol-toml/security/advisories/GHSA-r4xh-jqrq-34v2).
No parser override is needed. The CLI's configuration merge copies properties with
object spread, which accepts the parser's null-prototype results.

Markdownlint's rule normalization still checks `instanceof Object`, so the
[version-bound markdownlint patch](../patches/markdownlint@0.42.0.patch) accepts
null-prototype objects without changing previously accepted values. Without the
patch, nested TOML rule options silently lose their settings.

Retain the patch until markdownlint supports these objects. Verify removal with
`bun run test:markdownlint` and a fresh audit. The
[integration tests](../tests/markdownlint.test.mjs) cover actual CLI TOML config
pointers, nested and disabled rules, ignores, invalid input, many flat keys, and
existing YAML rules; the lock-graph regression checks the reviewed CLI version
and natural parser ownership.

Bun uses [lockfile format 3 for nested or version-scoped overrides](https://bun.sh/docs/pm/overrides#limitations).
The scoped RE2JS security override below requires this format. Do not edit the
format or integrity fields manually. Regenerate with the pinned executable and
verify that a subsequent `bun install --frozen-lockfile` succeeds without changing
the lockfile hash. When adding or removing an override, regenerate the lock with
`bun install` before using agent-tool's declared-dependency update helper, whose
frozen precheck intentionally refuses a manifest/lock mismatch.

## RE2JS security override

markdownlint 0.42.0 pins RE2JS 2.8.6. The version-scoped override selects the
minimal fixed patch, 2.8.7, for
[GHSA-gg6h-894w-4m9c](https://github.com/le0pard/re2js/security/advisories/GHSA-gg6h-894w-4m9c).
The advisory needs the opt-in `LOOKBEHINDS` flag; markdownlint does not enable
it, but retaining a known-vulnerable engine is unnecessary. The patched release
keeps the `re` tagged-template and `RE2JS.compile` APIs used by markdownlint.
The tests resolve the engine through its actual markdownlint owner, bound the
advisory's repeated matching case in a subprocess, and exercise front matter and
MD011, MD013, and MD039 through the CLI. Keep the override limited to this owner;
remove it when a supported markdownlint release naturally resolves a fixed
engine, then rerun those tests and the lockfile audit. No smol-toml override is
needed.

## Unresolved advisory constraints

KaTeX 0.16.47 remains affected by
[GHSA-238p-pmpm-9mq7](https://github.com/advisories/GHSA-238p-pmpm-9mq7): an
existing prototype pollution can bypass trust restrictions. The fix starts at
0.18.2, outside micromark-extension-math's `^0.16.0` range. Preserve that range
rather than force a cross-minor parser/rendering replacement. Repository-controlled
Markdown is the input. Remove this constraint when a supported owner upgrade or
backport resolves the finding, with math integration tests and a fresh audit.

The braces finding recorded in
[PR #400](https://github.com/a2f0/dotfiles/pull/400) was
[withdrawn upstream](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm); it is no
longer an active security exception. Recheck current advisories on every upgrade;
a successful lint run alone does not resolve an advisory.
