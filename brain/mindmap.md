---
slug: mindmap
title: Feature mindmap
role: feature mindmap
updated: "2026-09-18T18:09:56"
---

# Feature mindmap

## Feature mindmap

```mermaid
mindmap
  root((ownerrez-rate-setter))
    Guard
      Kill switch
      Modes and per-unit modes
      Permitted levers base and min
      Value sanity bounds
      Size cap
      Weekly frequency cap
      Cooldown
      Per-change approval
      Audit of every decision
    Writing
      Dry run by default
      Explicit execute
      Single mutating call
      Only changed fields sent
      Read-back verification
      Sync Now reminder
    Identity
      OwnerRez to PriceLabs map
      Ambiguous names refused
      Unmatched and orphans surfaced
    Rollback
      Rebuilt from audit log
      Restores pre-change value
      Still guarded
    Setup
      Init in SHADOW
      Credential presence check
      Map build
      Status
    Proof
      26 negative-leaning guard tests
      Sandboxed, no network
    Judgment
      Separate pricing reference
      Propose, never authorise
```

Pages behind the branches: [[fail-closed-write-guard]], [[shadow-by-default-and-write-modes]], [[approval-bound-to-one-change]], [[single-mutating-call-and-read-back]], [[identity-through-property-map]], [[rollback-from-audit-log]].
