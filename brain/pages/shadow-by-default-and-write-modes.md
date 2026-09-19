---
id: shadow-by-default-and-write-modes
title: "Start in read-only SHADOW; write authority only by a human config edit, global or per unit"
category: decision
status: active
tags: [modes, safety]
created: "2026-09-18T18:09:55"
updated: "2026-09-18T18:09:56"
---

<!-- compiled_truth -->
The tool installs in read-only SHADOW mode; write authority is granted only by a human editing local config, globally or per unit.

## Decision

Four modes, set in `.rate-setter/config.json`:

| Mode | Documented behaviour |
|---|---|
| `SHADOW` | Read-only: proposes, never writes. **The default** created by `setup.py --init`. |
| `APPROVE_EXECUTE` | Writes only after a named human approves each change. |
| `BOUNDED_AUTONOMY` | Writes within the caps without per-change approval. |
| `FULL_AUTONOMY` | Documented as writing without caps; "rarely the right answer". |

- `unit_modes` overrides the global mode for **exactly named** units, which is how one unit is piloted before trusting the portfolio. A name that does not match exactly falls back to the global mode — the restrictive direction, so a typo can never grant authority (tested).
- **No approval can override SHADOW** (tested).
- The skill **never advances its own mode**; enabling writes is the owner's deliberate edit.

## Rationale

"Installing a tool should never change your prices." Starting read-only means a fresh install, a misconfiguration or a curious agent cannot reprice anything.

## Open question (observed in code, 2026-09-18)

`guard.py` treats `BOUNDED_AUTONOMY` and `FULL_AUTONOMY` identically: size cap, frequency cap and cooldown apply in every write mode unless a valid explicit cap-override approval is supplied. So `FULL_AUTONOMY` currently does **not** write without caps as documented. The code is the stricter side; the owner should confirm which behaviour is intended and align docs or code.

Related: [[fail-closed-write-guard]], [[approval-bound-to-one-change]].


## Timeline

- time: 2026-09-18T18:09:55
  kind: decision
  summary: "Created this page: Start in read-only SHADOW; write authority only by a human config edit, global or per unit"
  source: "scripts/setup.py, scripts/guard.py, SKILL.md, README.md"
  affects: [shadow-by-default-and-write-modes]

- time: 2026-09-18T18:09:56
  kind: decision
  summary: Seeded from repository contents during brain bootstrap
  source: "SKILL.md, scripts/, README.md, git log"
  affects: [shadow-by-default-and-write-modes]
