---
id: approval-bound-to-one-change
title: Approvals bind to one exact change by a named human and expire
category: decision
status: active
tags: [approval, audit]
created: "2026-09-18T18:09:55"
updated: "2026-09-18T18:09:56"
---

<!-- compiled_truth -->
An approval authorises exactly one change — one unit, one field, one current value, one proposed value — from a named human, and expires after 15 minutes.

## Decision

- An `Approval` records unit, field, current value, proposed value, approver name, timestamp and whether caps are overridden. It **matches only that exact change**; approving a routine change can never silently authorise a different or larger one (tested: an approval for a different value is rejected).
- Approvals **expire after 15 minutes** (tested).
- **A plain approval does not override the caps.** Exceeding a cap needs a separate explicit `--override-caps` decision, also bound to the exact change (tested).
- In `APPROVE_EXECUTE`, `set_rates.py --execute` requires `--approved-by` and asks the operator to **type the unit name back**; `--yes` skips that prompt only for non-interactive runs of a change already approved.
- `--reason` is written to the permanent audit record, for a reader months later.

## Conduct rules for Claude (from `SKILL.md`)

- **You may propose. Only a named human may authorise.**
- Never add `--execute` on its own initiative — only when a human asked for *that specific change*; "take a look at pricing" is not authorisation.
- Never invent `--approved-by`: a name the person did not give is a falsified audit record.
- Never use `--override-caps` as a retry strategy; a denial is not an error — report it and stop.

## Rationale

The audit trail is only meaningful if each approval names a real person and binds to a single, visible change.

Related: [[fail-closed-write-guard]], [[shadow-by-default-and-write-modes]].


## Timeline

- time: 2026-09-18T18:09:55
  kind: decision
  summary: "Created this page: Approvals bind to one exact change by a named human and expire"
  source: "scripts/guard.py, scripts/set_rates.py, SKILL.md"
  affects: [approval-bound-to-one-change]

- time: 2026-09-18T18:09:56
  kind: decision
  summary: Seeded from repository contents during brain bootstrap
  source: "SKILL.md, scripts/, README.md, git log"
  affects: [approval-bound-to-one-change]
