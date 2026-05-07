---
name: deslopify-refactor
description: Behavior-preserving simplification and refactoring for codebases that may contain agent-written slop, duplication, wrappers, stale files, over-defensive branches, shallow tests, or accumulated complexity. Use when Codex is asked to de-slopify, simplify, reduce code, remove duplication, prune dead code, consolidate implementations, or refactor aggressively while proving that observable behavior, public contracts, security properties, side effects, and outputs are unchanged.
---

# De-slopify Refactor

Treat every simplification as a proof obligation: the smaller program must be observably equivalent to the larger one. Optimize for accretive reductions in code, duplication, and complexity, but do not call a change a refactor unless behavior preservation has been established.

## Core Rule

Only make a simplification when all three are true:

1. The change removes real complexity, duplication, dead surface area, or misleading scaffolding.
2. The intended equivalence boundary is explicit before editing.
3. Verification shows unchanged observable behavior, or unchanged pre-existing failures.

If equivalence cannot be proved at reasonable cost, reject or defer the candidate and record why.

## Workflow

### 1. Establish The Baseline

Start by understanding the repository and current state.

- Inspect `git status` and avoid overwriting user changes.
- Find project commands from package scripts, Makefiles, task files, CI config, or docs.
- Run the narrowest credible baseline: tests, typecheck, build, lint, or smoke commands.
- If baseline commands fail, record the exact pre-existing failures and continue only if the refactor can be verified against that same baseline.
- Capture golden behavior for touched surfaces when tests are weak: CLI output, API responses, rendered snapshots, serialized files, logs, database mutations in fixtures, or other observable outputs.
- Measure enough to prove value: LOC touched/removed, duplicate regions, complexity hotspots, warnings, generated artifacts, or stale entry points.

Do not edit before there is a baseline or a documented reason why one is unavailable.

### 2. Map Simplification Candidates

Search systematically instead of relying on taste.

- Use `rg`, language-aware search, dependency graphs, call references, test coverage, and clone tools when available.
- Classify duplication as exact copy-paste, parametric duplication, semantic similarity, or accidental resemblance.
- Prefer candidates with high confidence, small blast radius, and measurable reduction.
- Reject candidates that save little code, touch unclear contracts, or depend on unverified assumptions.
- Read `references/pathology-catalog.md` when scanning agent-written code for common simplification opportunities and traps.

Score each candidate before editing:

```text
value = expected code/complexity reduction
confidence = strength of proof that behavior is unchanged
risk = public API + side effects + async/lifecycle + security + data compatibility
```

Take high-value, high-confidence, low-risk candidates first. Log rejected or deferred candidates so future runs do not rediscover the same bad idea.

### 3. Write The Isomorphism Card

Before editing, define the exact equivalence claim. Use `references/isomorphism-card.md` for the checklist.

Keep the card short, but answer the rows that matter:

- Same inputs and outputs?
- Same public API, exports, status codes, errors, logs, metrics, and serialization?
- Same side effects, ordering, resource lifecycle, async cancellation, retries, and cleanup?
- Same React hook identity, memoization, dependency behavior, and effect cleanup when applicable?
- Same security boundary: auth, validation, escaping, permissions, crypto, SSRF/file/network constraints?

If any row is uncertain and relevant, either add characterization coverage first or do not perform the refactor.

### 4. Edit Narrowly

Use one lever per patch. A lever is a single simplification idea such as extracting a duplicated helper, deleting a proven-dead wrapper, merging two equivalent branches, or removing a stale compatibility shim.

- Keep public signatures, error semantics, side effects, ordering, and data formats stable.
- Prefer mechanical, local edits over broad rewrites.
- Add characterization tests before refactoring when existing tests do not cover the behavior at risk.
- Avoid new dependencies unless the repository already uses them and the simplification clearly justifies it.
- Do not delete apparently unused files in dynamic systems until entry points, imports, routes, config, build scripts, reflection, and deployment references are checked.
- Treat auth, permission checks, input validation, escaping, crypto, transactions, migrations, concurrency, retries, and cleanup as high-risk. Preserve them unless verification is strong.
- Do not mix cleanup with drive-by formatting, naming churn, dependency upgrades, or unrelated bug fixes.

### 5. Verify Equivalence

Run the same baseline commands after editing. Add targeted checks for the changed surface.

- Compare golden outputs byte-for-byte or semantically, depending on the contract.
- Confirm pre-existing failures are unchanged if the baseline was already red.
- Confirm no new warnings, build output changes, schema changes, generated files, or snapshots appeared unless expected and explained.
- If a test had to change, explain whether it is characterization coverage or an intentional update. Refactors should normally preserve tests.
- Revert the candidate if behavior changed and the user did not ask for a behavior change.

### 6. Record The Ledger

Maintain an audit trail for accepted, rejected, deferred, and reverted candidates. Use `references/ledger-template.md`.

For repeated work in the same repository, create or update `.codex/deslopify-ledger.md` unless the user disallows extra project files. For a one-off run, include the ledger in the final answer.

Each entry should include:

- Candidate and classification
- Equivalence claim
- Risk notes
- Files changed
- Verification commands and results
- LOC or complexity delta when practical
- Status: accepted, rejected, deferred, or reverted

## Output Discipline

When reporting results, lead with what changed and how equivalence was verified. Mention rejected candidates only when they matter for auditability or future work. If verification was incomplete, say exactly what was not proved.
