# Agent-Code Pathology Catalog

Use this to find simplification candidates and avoid common false positives.

## High-Confidence Candidates

| Pathology | Typical signal | Safe simplification |
| --- | --- | --- |
| Exact copy-paste | Same blocks across files with identical inputs and side effects | Extract a shared helper or consolidate call sites after proving ordering and errors match |
| Thin wrapper cascade | Functions pass through arguments without adding behavior | Inline or remove wrappers only after checking logs, metrics, error wrapping, binding, decorators, and public imports |
| Duplicate constants/config | Same literals repeated for one concept | Centralize if load order, tree shaking, environment overrides, and serialization are unaffected |
| Comments as task plans | Comments describe past implementation intent, not current behavior | Delete stale planning comments while preserving useful rationale and API docs |
| Dead private branch | Internal branch is unreachable by type, exhaustive caller analysis, and tests | Remove with characterization coverage if behavior is otherwise untested |
| Parametric duplication | Same algorithm with small literal differences | Extract parameterized helper when names, errors, side effects, and performance remain clear |

## Medium-Risk Candidates

| Pathology | Risk | Guardrail |
| --- | --- | --- |
| Over-defensive branches | "Impossible" inputs may be part of a public contract | Remove only for internal code or after proving callers and documented behavior exclude the case |
| Over-parameterized helpers | Optional knobs may support hidden callers | Collapse only after checking all call sites, config, tests, generated code, and external API boundaries |
| Stale types or schemas | Generated code, migrations, API clients, or docs may depend on them | Verify generation sources and consumers before deleting |
| Parallel v1/v2 files | Old-looking file may still be the deployment entry point | Check imports, routes, package exports, build config, runtime discovery, and CI |
| Try/catch clutter | Catch blocks may normalize errors, logs, metrics, cleanup, or retries | Preserve thrown values and side effects exactly, or leave the catch alone |
| Shallow happy-path tests | Existing tests do not prove edge behavior | Add characterization tests around the risky behavior before simplifying |

## High-Risk Candidates

Avoid these unless verification is strong and focused:

- Auth, authorization, permission checks, session handling, secret handling
- Input validation, escaping, sanitization, path/file/network boundaries
- Crypto, hashing, signatures, token generation, random IDs
- Transactions, migrations, locking, concurrency, retry logic, idempotency
- Async cancellation, stream handling, lifecycle cleanup, subscriptions
- React hook order, effect dependencies, memoized identity, controlled/uncontrolled state
- Serialization formats used by external clients, caches, databases, queues, or snapshots

## Candidate Scoring

Use this quick scoring model:

```text
value:      1 low, 2 medium, 3 high
confidence: 1 weak, 2 plausible, 3 proven
risk:       1 low, 2 medium, 3 high

take first: value + confidence >= 5 and risk <= 2
defer:      confidence < 2 or risk == 3
reject:     value == 1 and risk >= 2
```

The scoring is a forcing function, not a substitute for judgment. A small, obvious deletion with perfect proof can still be worthwhile; a large deletion with unclear behavior should still be rejected.
