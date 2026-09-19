---
id: rollback-from-audit-log
title: "Rollback rebuilt from the audit log, restoring the pre-change value, still guarded"
category: decision
status: active
tags: [rollback, audit]
created: "2026-09-18T18:09:55"
updated: "2026-09-18T18:09:56"
---

<!-- compiled_truth -->
Rollback is reconstructed from the audit log, restores the value held before the earliest change in scope, and still goes through the guard.

## Decision

- `rollback.py` selects successfully applied changes by `--unit`, `--run-id` and/or `--since`, and plans by default; `--execute` applies.
- For each unit and field it restores the value held **before the earliest change in scope** — not a chain of intermediate steps.
- It is **not a side door**: each restore is a normal guarded write (mode, caps, approval), pushed through the single mutating call and read back ([[single-mutating-call-and-read-back]]). An active **kill switch blocks rollback** too: a halted system should not write at all, even to restore.
- `--approved-by` is required when any unit in scope is in `APPROVE_EXECUTE`, or when `--emergency` is passed. Units that can no longer be resolved are skipped and counted as failed.

## Rationale

The audit log already holds every applied change with its before and after values, so undo needs no separate state, and routing it through the guard keeps one set of rules for every write.

## Open question (observed in code, 2026-09-18)

`SKILL.md` and the `rollback.py` docstring say `--emergency` clears **the cooldown and frequency caps only** (never the kill switch or the mode). In code, `--emergency` builds an approval with `override_caps` set, and the guard's override skips the **size cap as well** as the frequency cap and cooldown. Kill switch and mode are still enforced as documented. The owner should confirm whether emergency rollbacks are meant to bypass the size cap, and align docs or code.

Related: [[fail-closed-write-guard]], [[approval-bound-to-one-change]], [[identity-through-property-map]].


## Timeline

- time: 2026-09-18T18:09:55
  kind: decision
  summary: "Created this page: Rollback rebuilt from the audit log, restoring the pre-change value, still guarded"
  source: "scripts/rollback.py, SKILL.md"
  affects: [rollback-from-audit-log]

- time: 2026-09-18T18:09:56
  kind: decision
  summary: Seeded from repository contents during brain bootstrap
  source: "SKILL.md, scripts/, README.md, git log"
  affects: [rollback-from-audit-log]
