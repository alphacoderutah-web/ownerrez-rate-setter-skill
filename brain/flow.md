---
slug: flow
title: Key flows
role: key flows
updated: "2026-09-18T18:09:56"
---

# Key flows

## End-to-end path of a typical request

A human asks for one rate change on one unit, in `APPROVE_EXECUTE` mode:

```mermaid
sequenceDiagram
  participant H as Human
  participant C as Claude
  participant T as set_rates.py
  participant G as guard.py
  participant M as property map
  participant P as PriceLabs API
  H->>C: Asks for a specific change on a named unit
  C->>T: Dry run (no --execute)
  T->>M: Resolve unit name, refuse if ambiguous
  T->>P: GET live listing values
  T->>G: check_write per field (audited)
  G-->>T: Verdict + reasons
  T-->>C: Live values, mode, proposed change, verdicts
  C-->>H: Shows verdict; asks for authorisation of this exact change
  H-->>C: Authorises, gives own name
  C->>T: Re-run with execute, a reason and the approver's name
  T-->>H: Type the unit name back to confirm
  H-->>T: Confirms
  T->>G: check_write with an Approval bound to this change
  G-->>T: Allowed
  T->>P: POST only the changed fields (single call)
  T->>G: record_applied (counts toward caps)
  T->>P: GET and compare (read-back)
  T-->>C: Confirmed live, or MISMATCH (stop and investigate)
  C-->>H: Result + reminder to press Sync Now in PriceLabs
```

## Other important flows

- **Denial.** Report the guard's reason and stop. Do not retry, and do not search for a flag that turns the answer into yes. Each verdict type calls for a specific response, set out in `SKILL.md`.
- **First-time setup.** `setup.py --init` creates config in SHADOW; `--check` confirms credential presence and API connectivity; `--map` builds the identity map, listing unmatched properties and orphan listings; `--status` summarises mode, caps, map and audit.
- **Emergency stop.** Engaging the kill switch writes `.rate-setter/KILL-SWITCH`; every write, including rollback, halts until a human deletes it after understanding why.
- **Rollback.** Plan first, then `--execute` with approval where required. Values are restored through the same guard, push and read-back path. See [[rollback-from-audit-log]].
- **Piloting.** `unit_modes` grants write authority to one named unit while the rest of the portfolio stays in the global mode. See [[shadow-by-default-and-write-modes]].
