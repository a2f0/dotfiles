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

Keep Python on 3.14 while Ansible uses core 2.21: its
[support matrix](https://docs.ansible.com/projects/ansible-core/devel/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix)
supports controller Python 3.12–3.14 and target Python 3.9–3.14. Python 3.15
requires a stable compatible Ansible/core release, followed by the complete
guarded previews and controller/target checks below.

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
Removing the last such override can return the generated lockfile to format 2,
even with the same pinned Bun 1.4.3. Do not edit the format or integrity fields
manually. Regenerate with the pinned executable and verify that a subsequent
`bun install --frozen-lockfile` succeeds without changing the lockfile hash.

## Unresolved advisory constraints

[PR #400](https://github.com/a2f0/dotfiles/pull/400) recorded unresolved advisories
for [braces 3.0.3](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) and
[KaTeX 0.16.47](https://github.com/advisories/GHSA-238p-pmpm-9mq7). At that review,
braces had no published patched version, and markdownlint's math extension
constrained KaTeX to `^0.16.0`. Repository-controlled lint patterns and Markdown
are their inputs. These explain the retained dependency choices; they are not a
fresh audit or a claim about today's upstream releases.

Recheck both advisories and their owning dependency ranges on the next upgrade.
Remove these constraints once a supported owner upgrade or compatible targeted
refresh resolves them and a fresh audit confirms the result. A successful lint
run does not resolve an advisory; do not force an unsupported replacement to
silence the audit.
