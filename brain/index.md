# Brain Index

_Auto-generated. Last updated 2026-09-19T00:09:57.056Z._

- [approval-bound-to-one-change](pages/approval-bound-to-one-change.md) — category: decision | tags: [approval, audit] | An approval authorises exactly one change — one unit, one field, one current value, one proposed value — from a named human, and expires aft
- [fail-closed-write-guard](pages/fail-closed-write-guard.md) — category: decision | tags: [guard, safety] | Every rate change passes through one guard that evaluates fixed checks in order, denies on any uncertainty, and audits every decision.
- [identity-through-property-map](pages/identity-through-property-map.md) — category: decision | tags: [identity, ownerrez] | Units are resolved only through a pinned OwnerRez-to-PriceLabs property map built by exact id join; ambiguous names are refused, never guess
- [rollback-from-audit-log](pages/rollback-from-audit-log.md) — category: decision | tags: [rollback, audit] | Rollback is reconstructed from the audit log, restores the value held before the earliest change in scope, and still goes through the guard.
- [shadow-by-default-and-write-modes](pages/shadow-by-default-and-write-modes.md) — category: decision | tags: [modes, safety] | The tool installs in read-only SHADOW mode; write authority is granted only by a human editing local config, globally or per unit.
- [single-mutating-call-and-read-back](pages/single-mutating-call-and-read-back.md) — category: decision | tags: [pricelabs, verification] | Exactly one function may write to PriceLabs; it sends only the fields being changed, and every write is read back because a success response
