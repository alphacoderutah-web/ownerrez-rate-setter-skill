---
id: single-mutating-call-and-read-back
title: "One mutating PriceLabs call, changed fields only, verified by read-back"
category: decision
status: active
tags: [pricelabs, verification]
created: "2026-09-18T18:09:55"
updated: "2026-09-18T18:09:56"
---

<!-- compiled_truth -->
Exactly one function may write to PriceLabs; it sends only the fields being changed, and every write is read back because a success response is not proof.

## Decision

- `pricelabs.push_price` is the **only mutating call** in the package, so there is one place to audit.
- It sends **only the changed fields** (base and/or minimum) for the one listing; base and minimum changes for a unit travel in a **single POST** so they move together.
- After a successful push, `verify` re-reads the account's listings and compares each written field; any mismatch is printed and the run exits non-zero with an instruction to **investigate before making further changes**, not to retry.
- On success the tool reminds the human to press **Sync Now** in PriceLabs, because otherwise changes can take about a day to reach channels — long enough for someone to think the change failed and cut again.

## API hazards this design answers (documented in `pricelabs.py`)

1. **The write path is the read path**: the same listings endpoint reads on GET and writes on POST, so a verb typo is the difference between listing and repricing. Hence the single POST site.
2. **Omitted vs null**: an omitted field is left unchanged, but a field sent as null is cleared; building the payload from the full listing object would eventually wipe a minimum. Hence changed-fields-only payloads.

## Rationale

"A `200` is not proof the value stuck." Verification is at the layer being claimed — the live PriceLabs value — rather than the HTTP status.

Related: [[fail-closed-write-guard]], [[rollback-from-audit-log]].


## Timeline

- time: 2026-09-18T18:09:55
  kind: decision
  summary: "Created this page: One mutating PriceLabs call, changed fields only, verified by read-back"
  source: "scripts/pricelabs.py, scripts/set_rates.py, git log"
  affects: [single-mutating-call-and-read-back]

- time: 2026-09-18T18:09:56
  kind: decision
  summary: Seeded from repository contents during brain bootstrap
  source: "SKILL.md, scripts/, README.md, git log"
  affects: [single-mutating-call-and-read-back]
