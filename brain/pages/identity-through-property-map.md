---
id: identity-through-property-map
title: "Resolve units through a pinned id-joined property map; refuse ambiguity"
category: decision
status: active
tags: [identity, ownerrez]
created: "2026-09-18T18:09:55"
updated: "2026-09-18T18:09:56"
---

<!-- compiled_truth -->
Units are resolved only through a pinned OwnerRez-to-PriceLabs property map built by exact id join; ambiguous names are refused, never guessed.

## Decision

- `setup.py --map` builds `.rate-setter/property-map.json` per account by joining OwnerRez properties to PriceLabs listings **on id**: when the PMS is OwnerRez, PriceLabs stores the OwnerRez property id as its listing id, which makes an exact join possible.
- Anything that does not join is **surfaced, not force-matched**: active OwnerRez properties with no PriceLabs listing ("cannot be repriced") and PriceLabs listings with no OwnerRez property ("orphans", flagged if hidden).
- `resolve(name)` tries an exact name, then an unambiguous case-insensitive match, then an unambiguous partial match. **More than one candidate raises an error listing the candidates**; an unknown name says to rebuild the map. A unit with no PriceLabs listing is refused ("nothing to write to").

## Alternatives rejected

- **Resolving by eyeballing or string-matching a name.** Names repeat across accounts, the two systems use different identifiers, and one physical home is sometimes listed twice (for example one channel-only record per channel). String matching "is how the wrong property gets repriced".

## Evidence

The commit message reports that, in live verification before release, the map matched every property, flagged the one orphaned listing, and refused an ambiguous name with candidates listed.

Related: [[fail-closed-write-guard]], [[rollback-from-audit-log]].


## Timeline

- time: 2026-09-18T18:09:55
  kind: decision
  summary: "Created this page: Resolve units through a pinned id-joined property map; refuse ambiguity"
  source: "scripts/properties.py, SKILL.md, git log"
  affects: [identity-through-property-map]

- time: 2026-09-18T18:09:56
  kind: decision
  summary: Seeded from repository contents during brain bootstrap
  source: "SKILL.md, scripts/, README.md, git log"
  affects: [identity-through-property-map]
