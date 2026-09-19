---
id: fail-closed-write-guard
title: "One write guard, ordered checks, fails closed, audits every decision"
category: decision
status: active
tags: [guard, safety]
created: "2026-09-18T18:09:55"
updated: "2026-09-18T18:09:56"
---

<!-- compiled_truth -->
Every rate change passes through one guard that evaluates fixed checks in order, denies on any uncertainty, and audits every decision.

## Decision

`guard.check_write` is the single choke point. It never performs a change itself; it returns a verdict. Checks run in this order, and the first failure denies:

1. **Kill switch present** → deny everything, unconditionally.
2. **Mode** (per-unit or global) → SHADOW denies all writes ([[shadow-by-default-and-write-modes]]).
3. **Permitted lever** → only base and minimum may be written; the maximum-price field is refused in code, and any other field is unknown and refused.
4. **Value sanity** → non-numeric, non-positive, out-of-bounds or no-op values are denied.
5. **Size cap** → a change larger than the configured percentage needs explicit approval.
6. **Frequency cap** → too many applied changes to that unit and field in the last 7 days needs approval.
7. **Cooldown** → a change inside the cooldown window is denied (a change needs time to show an effect).
8. **APPROVE_EXECUTE** → a matching, unexpired, named approval is required ([[approval-bound-to-one-change]]).

## Fail-closed rules

- Missing or unreadable config, a missing `mode`/`caps`/size cap, or any exception inside the guard → `GUARD FAILED CLOSED`, a denial. A default cap is "a cap nobody chose", so there is no silent fallback.
- **Every decision is audited** (allowed and denied) to `write-audit.jsonl`; an audit write failure is swallowed so it can never mask the decision itself.
- **Only applied changes count toward the caps**, so denied attempts cannot exhaust the weekly allowance; recording an "applied" event for a denied decision raises an error.
- Cap values live in local config and are adjustable; the maximum-price prohibition is not.

## Alternatives rejected

- **Checks scattered across CLIs** — one choke point is one place to audit and test.
- **Fail open with defaults** — explicitly rejected in `config.py` and `guard.py`.

## Evidence

`test_guard.py` covers these paths with 26 sandboxed cases, mostly negative (kill switch, SHADOW, oversized and too-frequent changes, cooldown, malformed values, missing and corrupt config, approval matching and expiry, cap overrides, per-unit mode isolation, audit). 26/26 passed on 2026-09-18.


## Timeline

- time: 2026-09-18T18:09:55
  kind: decision
  summary: "Created this page: One write guard, ordered checks, fails closed, audits every decision"
  source: "scripts/guard.py, scripts/config.py, scripts/test_guard.py"
  affects: [fail-closed-write-guard]

- time: 2026-09-18T18:09:56
  kind: decision
  summary: Seeded from repository contents during brain bootstrap
  source: "SKILL.md, scripts/, README.md, git log"
  affects: [fail-closed-write-guard]
