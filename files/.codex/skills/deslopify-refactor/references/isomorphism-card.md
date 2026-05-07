# Isomorphism Card

Use this before editing. Complete only the rows relevant to the candidate, but do not skip a relevant row because it is inconvenient.

## Candidate

- Candidate:
- Intended simplification:
- Files/functions:
- Public or internal surface:
- Expected reduction:
- Baseline evidence:

## Equivalence Checklist

| Dimension | Question | Evidence |
| --- | --- | --- |
| Inputs | Are accepted inputs, defaults, coercions, validation, and invalid-input handling unchanged? | |
| Outputs | Are return values, response bodies, rendered output, file contents, exit codes, and snapshots unchanged? | |
| Public API | Are exports, function signatures, routes, CLI flags, config keys, types, schemas, and documented behavior unchanged? | |
| Error semantics | Are thrown classes, messages, status codes, error wrapping, retries, fallbacks, and stack exposure unchanged? | |
| Side effects | Are writes, network calls, cache mutations, events, notifications, metrics, traces, and logs unchanged? | |
| Ordering | Does evaluation order remain the same where side effects, logs, mutation, hooks, or timing can be observed? | |
| Async behavior | Are cancellation, races, timers, backpressure, retry timing, promise rejection timing, and cleanup unchanged? | |
| Resource lifecycle | Are files, sockets, locks, transactions, subscriptions, handles, temp files, and cleanup paths preserved? | |
| React/UI lifecycle | Are hook order, dependency arrays, memo identity, refs, effect cleanup, controlled state, and render timing unchanged? | |
| Serialization | Are key order, date/time formatting, locales, precision, null/undefined handling, and compatibility formats unchanged? | |
| Security boundary | Are auth, authorization, validation, escaping, sanitization, CSRF, SSRF, path traversal, crypto, and secret handling unchanged? | |
| Compatibility | Are dynamic imports, reflection, plugin discovery, naming conventions, generated code, and deployment entry points preserved? | |
| Performance contract | If performance is part of the contract, are complexity, batching, caching, memory, and I/O behavior preserved or improved? | |

## Decision

- Status: accepted / rejected / deferred
- Reason:
- Required verification:
- Rollback trigger:
